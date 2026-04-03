from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from flask import Flask, jsonify, redirect, render_template, request, url_for, flash

app = Flask(__name__)
app.secret_key = "barcode-inventory-local"

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "inventory_data.json"


def default_data() -> dict:
    return {"next_floor_id": 1, "floors": []}


def normalize_barcode(value: str) -> str:
    return value.strip()


def load_data() -> dict:
    if not DATA_FILE.exists():
        data = default_data()
        save_data(data)
        return data

    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        data = default_data()
        save_data(data)
        return data

    if not isinstance(data, dict):
        data = default_data()

    data.setdefault("next_floor_id", 1)
    data.setdefault("floors", [])

    # Repair old/bad structures safely
    repaired_floors = []
    seen_ids = set()
    max_id = 0
    for floor in data.get("floors", []):
        if not isinstance(floor, dict):
            continue
        floor_id = floor.get("id")
        name = str(floor.get("name", "")).strip()
        items = floor.get("items", [])

        if not isinstance(floor_id, int):
            continue
        if not name:
            continue
        if floor_id in seen_ids:
            continue

        if not isinstance(items, list):
            items = []
        clean_items = []
        seen_codes = set()
        for code in items:
            code = normalize_barcode(str(code))
            if code and code not in seen_codes:
                clean_items.append(code)
                seen_codes.add(code)

        repaired_floors.append({
            "id": floor_id,
            "name": name,
            "items": clean_items,
        })
        seen_ids.add(floor_id)
        max_id = max(max_id, floor_id)

    data["floors"] = repaired_floors
    if not isinstance(data.get("next_floor_id"), int) or data["next_floor_id"] <= max_id:
        data["next_floor_id"] = max_id + 1 if max_id else 1

    return data


def save_data(data: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", delete=False, dir=DATA_FILE.parent, encoding="utf-8") as tmp:
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp.flush()
        temp_name = tmp.name
    Path(temp_name).replace(DATA_FILE)


def get_floor_or_none(data: dict, floor_id: int) -> dict | None:
    for floor in data["floors"]:
        if floor["id"] == floor_id:
            return floor
    return None


@app.route("/")
def index():
    data = load_data()
    floors = sorted(data["floors"], key=lambda x: x["name"].lower())
    total_items = sum(len(floor["items"]) for floor in floors)
    return render_template("index.html", floors=floors, total_items=total_items)


@app.route("/floors", methods=["POST"])
def create_floor():
    floor_name = request.form.get("floor_name", "").strip()
    if not floor_name:
        flash("Floor name cannot be empty.", "error")
        return redirect(url_for("index"))

    data = load_data()
    existing = next((f for f in data["floors"] if f["name"].lower() == floor_name.lower()), None)
    if existing:
        flash(f'"{existing["name"]}" already exists.', "error")
        return redirect(url_for("floor_detail", floor_id=existing["id"]))

    floor = {
        "id": data["next_floor_id"],
        "name": floor_name,
        "items": [],
    }
    data["floors"].append(floor)
    data["next_floor_id"] += 1
    save_data(data)

    flash(f'Floor "{floor_name}" created.', "success")
    return redirect(url_for("floor_detail", floor_id=floor["id"]))


@app.route("/floors/<int:floor_id>")
def floor_detail(floor_id: int):
    data = load_data()
    floor = get_floor_or_none(data, floor_id)
    if floor is None:
        flash("Floor not found.", "error")
        return redirect(url_for("index"))

    items = sorted(floor["items"])
    return render_template(
        "floor.html",
        floor=floor,
        items=items,
        total_items=len(items),
    )


@app.route("/floors/<int:floor_id>/scan", methods=["POST"])
def scan_item(floor_id: int):
    data = load_data()
    floor = get_floor_or_none(data, floor_id)
    if floor is None:
        return jsonify({"status": "error", "message": "Floor not found."}), 404

    if request.is_json:
        payload = request.get_json(silent=True) or {}
        barcode = normalize_barcode(str(payload.get("barcode", "")))
    else:
        barcode = normalize_barcode(request.form.get("barcode", ""))

    if not barcode:
        return jsonify({"status": "error", "message": "Empty barcode."}), 400

    if barcode in floor["items"]:
        return jsonify({
            "status": "duplicate",
            "message": "This barcode is already saved on this floor.",
            "barcode": barcode,
            "total_items": len(floor["items"]),
        })

    floor["items"].append(barcode)
    save_data(data)

    return jsonify({
        "status": "success",
        "message": "Barcode added.",
        "barcode": barcode,
        "total_items": len(floor["items"]),
    })


@app.route("/floors/<int:floor_id>/delete-item", methods=["POST"])
def delete_item(floor_id: int):
    data = load_data()
    floor = get_floor_or_none(data, floor_id)
    if floor is None:
        flash("Floor not found.", "error")
        return redirect(url_for("index"))

    barcode = normalize_barcode(request.form.get("barcode", ""))
    if not barcode:
        flash("Barcode not provided.", "error")
        return redirect(url_for("floor_detail", floor_id=floor_id))

    if barcode in floor["items"]:
        floor["items"].remove(barcode)
        save_data(data)
        flash(f"Barcode {barcode} removed.", "success")
    else:
        flash("Barcode not found on this floor.", "error")

    return redirect(url_for("floor_detail", floor_id=floor_id))


@app.route("/floors/<int:floor_id>/delete", methods=["POST"])
def delete_floor(floor_id: int):
    data = load_data()
    floor = get_floor_or_none(data, floor_id)
    if floor is None:
        flash("Floor not found.", "error")
        return redirect(url_for("index"))

    data["floors"] = [f for f in data["floors"] if f["id"] != floor_id]
    save_data(data)
    flash(f'Floor "{floor["name"]}" deleted.', "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    # debug=False avoids the reloader creating confusion while scanning around the office
    app.run(host="127.0.0.1", port=5000, debug=False)
