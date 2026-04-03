# Barcode Inventory App

Local Flask app to track monitors or any barcoded items by floor/department/...

## Features
- Create floors
- Scan barcodes into a selected floor
- Prevent duplicate barcodes on the same floor
- Remove a wrongly scanned barcode
- Delete a whole floor
- Save everything in `inventory_data.json`
- Data persists after closing and reopening the app

## Important
The JSON file is saved next to `app.py`, so your data stays in the project folder even if you run the app from another directory.

## Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open:
```text
http://127.0.0.1:5000
```

## Scanner usage
Most USB barcode scanners behave like a keyboard:
1. Open a floor
2. Click once inside the scan box
3. Scan
4. If your scanner sends Enter automatically, the barcode is saved instantly

## Example barcode
`MMTKVEE00622312A443W01`
