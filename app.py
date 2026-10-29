# """
# Blood Bank Management System
# Module 1: Donor Management
# Module 2: Blood Inventory Management
# Integration: a donation links a donor to a blood unit, updates donor history,
# and updates stock.  Database: data.json (no SQL).
# Run:  pip install flask  ->  python app.py  ->  open http://127.0.0.1:5000
# """
# import json
# import os
# import re
# import threading
# from datetime import date, datetime, timedelta
#
# from flask import Flask, jsonify, request, send_from_directory
#
# app = Flask(__name__, static_folder="static")
# DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
# LOCK = threading.Lock()
#
# BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
# GENDERS = ["Male", "Female", "Other"]
# MIN_AGE, MAX_AGE = 18, 65
# MIN_WEIGHT = 50          # kg
# MIN_HB, MAX_HB = 12.5, 20.0  # g/dL
# DONATION_GAP_DAYS = 90   # days between two donations
# SHELF_LIFE_DAYS = 35     # blood unit expiry
# LOW_STOCK_LIMIT = 5      # units
#
#
# # ---------------------------------------------------------------- JSON "database"
# def load_db():
#     if not os.path.exists(DB_FILE):
#         return {"donors": [], "inventory": [], "next_donor_id": 1, "next_unit_id": 1}
#     with open(DB_FILE, "r", encoding="utf-8") as f:
#         return json.load(f)
#
#
# def save_db(db):
#     with open(DB_FILE, "w", encoding="utf-8") as f:
#         json.dump(db, f, indent=2)
#
#
# def err(msg, code=400, errors=None):
#     body = {"error": msg}
#     if errors:
#         body["errors"] = errors
#     return jsonify(body), code
#
#
# # ---------------------------------------------------------------- validation
# def validate_donor(data, db, donor_id=None):
#     """Return list of error strings (empty list = valid)."""
#     errors = []
#
#     name = str(data.get("name", "")).strip()
#     if not name:
#         errors.append("Name is required.")
#     elif not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,49}", name):
#         errors.append("Name must be 2-50 letters (no digits).")
#
#     try:
#         age = int(data.get("age"))
#         if age < MIN_AGE or age > MAX_AGE:
#             errors.append(f"Age must be between {MIN_AGE} and {MAX_AGE}.")
#     except (TypeError, ValueError):
#         errors.append("Age must be a whole number.")
#
#     if data.get("gender") not in GENDERS:
#         errors.append("Gender must be Male, Female or Other.")
#
#     if data.get("blood_group") not in BLOOD_GROUPS:
#         errors.append("Invalid blood group.")
#
#     try:
#         weight = float(data.get("weight"))
#         if weight < MIN_WEIGHT:
#             errors.append(f"Weight must be at least {MIN_WEIGHT} kg.")
#         elif weight > 200:
#             errors.append("Weight must be 200 kg or less.")
#     except (TypeError, ValueError):
#         errors.append("Weight must be a number.")
#
#     try:
#         hb = float(data.get("hemoglobin"))
#         if hb < MIN_HB or hb > MAX_HB:
#             errors.append(f"Hemoglobin must be between {MIN_HB} and {MAX_HB} g/dL.")
#     except (TypeError, ValueError):
#         errors.append("Hemoglobin must be a number.")
#
#     phone = str(data.get("phone", "")).strip()
#     if not re.fullmatch(r"[6-9]\d{9}", phone):
#         errors.append("Phone must be 10 digits and start with 6, 7, 8 or 9.")
#     else:
#         for d in db["donors"]:
#             if d["phone"] == phone and d["id"] != donor_id:
#                 errors.append("A donor with this phone number already exists.")
#                 break
#
#     email = str(data.get("email", "")).strip()
#     if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
#         errors.append("Email format is invalid.")
#
#     return errors
#
#
# def find_donor(db, donor_id):
#     return next((d for d in db["donors"] if d["id"] == donor_id), None)
#
#
# def unit_status(unit):
#     if unit["status"] == "Issued":
#         return "Issued"
#     if date.fromisoformat(unit["expiry_date"]) < date.today():
#         return "Expired"
#     return "Available"
#
#
# # ---------------------------------------------------------------- pages
# @app.route("/")
# def home():
#     return send_from_directory("static", "index.html")
#
#
# # ================================================================ MODULE 1: DONORS
# @app.route("/api/donors", methods=["GET"])
# def list_donors():
#     db = load_db()
#     donors = db["donors"]
#     bg = request.args.get("blood_group")
#     q = request.args.get("q", "").strip().lower()
#     if bg:
#         donors = [d for d in donors if d["blood_group"] == bg]
#     if q:
#         donors = [d for d in donors if q in d["name"].lower() or q in d["phone"]]
#     return jsonify(donors)
#
#
# @app.route("/api/donors", methods=["POST"])
# def add_donor():
#     data = request.get_json(silent=True) or {}
#     with LOCK:
#         db = load_db()
#         errors = validate_donor(data, db)
#         if errors:
#             return err("Validation failed", 400, errors)
#         donor = {
#             "id": db["next_donor_id"],
#             "name": data["name"].strip(),
#             "age": int(data["age"]),
#             "gender": data["gender"],
#             "blood_group": data["blood_group"],
#             "weight": float(data["weight"]),
#             "hemoglobin": float(data["hemoglobin"]),
#             "phone": str(data["phone"]).strip(),
#             "email": str(data.get("email", "")).strip(),
#             "registered_on": date.today().isoformat(),
#             "last_donation_date": None,
#             "donation_count": 0,
#         }
#         db["next_donor_id"] += 1
#         db["donors"].append(donor)
#         save_db(db)
#     return jsonify(donor), 201
#
#
# @app.route("/api/donors/<int:donor_id>", methods=["PUT"])
# def update_donor(donor_id):
#     data = request.get_json(silent=True) or {}
#     with LOCK:
#         db = load_db()
#         donor = find_donor(db, donor_id)
#         if not donor:
#             return err("Donor not found", 404)
#         errors = validate_donor(data, db, donor_id)
#         if errors:
#             return err("Validation failed", 400, errors)
#         donor.update({
#             "name": data["name"].strip(),
#             "age": int(data["age"]),
#             "gender": data["gender"],
#             "blood_group": data["blood_group"],
#             "weight": float(data["weight"]),
#             "hemoglobin": float(data["hemoglobin"]),
#             "phone": str(data["phone"]).strip(),
#             "email": str(data.get("email", "")).strip(),
#         })
#         save_db(db)
#     return jsonify(donor)
#
#
# @app.route("/api/donors/<int:donor_id>", methods=["DELETE"])
# def delete_donor(donor_id):
#     with LOCK:
#         db = load_db()
#         donor = find_donor(db, donor_id)
#         if not donor:
#             return err("Donor not found", 404)
#         if any(u["donor_id"] == donor_id and unit_status(u) == "Available"
#                for u in db["inventory"]):
#             return err("Cannot delete: donor has blood units still in stock.", 409)
#         db["donors"].remove(donor)
#         save_db(db)
#     return jsonify({"message": "Donor deleted"})
#
#
# @app.route("/api/donors/<int:donor_id>/eligibility", methods=["GET"])
# def eligibility(donor_id):
#     db = load_db()
#     donor = find_donor(db, donor_id)
#     if not donor:
#         return err("Donor not found", 404)
#     ok, reason = check_eligible(donor)
#     return jsonify({"eligible": ok, "reason": reason})
#
#
# def check_eligible(donor):
#     if donor["last_donation_date"]:
#         last = date.fromisoformat(donor["last_donation_date"])
#         next_ok = last + timedelta(days=DONATION_GAP_DAYS)
#         if date.today() < next_ok:
#             return False, f"Last donated on {last}. Eligible again on {next_ok}."
#     return True, "Eligible to donate."
#
#
# # ================================================================ MODULE 2: INVENTORY
# @app.route("/api/inventory", methods=["GET"])
# def list_inventory():
#     db = load_db()
#     units = []
#     for u in db["inventory"]:
#         row = dict(u)
#         row["status"] = unit_status(u)
#         units.append(row)
#     bg = request.args.get("blood_group")
#     st = request.args.get("status")
#     if bg:
#         units = [u for u in units if u["blood_group"] == bg]
#     if st:
#         units = [u for u in units if u["status"] == st]
#     return jsonify(units)
#
#
# @app.route("/api/inventory/summary", methods=["GET"])
# def stock_summary():
#     db = load_db()
#     summary = {bg: 0 for bg in BLOOD_GROUPS}
#     expiring_soon = []
#     for u in db["inventory"]:
#         if unit_status(u) == "Available":
#             summary[u["blood_group"]] += 1
#             days_left = (date.fromisoformat(u["expiry_date"]) - date.today()).days
#             if days_left <= 7:
#                 expiring_soon.append({"unit_id": u["id"], "blood_group": u["blood_group"],
#                                       "days_left": days_left})
#     low = [bg for bg, n in summary.items() if n < LOW_STOCK_LIMIT]
#     return jsonify({"stock": summary, "low_stock": low, "expiring_soon": expiring_soon,
#                     "low_stock_limit": LOW_STOCK_LIMIT})
#
#
# @app.route("/api/inventory", methods=["POST"])
# def record_donation():
#     """INTEGRATION POINT: donation -> checks donor (module 1) -> adds unit (module 2)
#     -> updates donor history (module 1)."""
#     data = request.get_json(silent=True) or {}
#     try:
#         donor_id = int(data.get("donor_id"))
#     except (TypeError, ValueError):
#         return err("donor_id is required and must be a number.")
#
#     try:
#         volume = int(data.get("volume_ml", 350))
#         if volume < 300 or volume > 500:
#             return err("Volume must be between 300 and 500 ml.")
#     except (TypeError, ValueError):
#         return err("Volume must be a number.")
#
#     with LOCK:
#         db = load_db()
#         donor = find_donor(db, donor_id)
#         if not donor:
#             return err("Donor not found", 404)
#         ok, reason = check_eligible(donor)
#         if not ok:
#             return err(reason, 409)
#
#         today = date.today()
#         unit = {
#             "id": db["next_unit_id"],
#             "donor_id": donor_id,
#             "donor_name": donor["name"],
#             "blood_group": donor["blood_group"],
#             "volume_ml": volume,
#             "collection_date": today.isoformat(),
#             "expiry_date": (today + timedelta(days=SHELF_LIFE_DAYS)).isoformat(),
#             "status": "Available",
#             "issued_to": None,
#             "issued_on": None,
#         }
#         db["next_unit_id"] += 1
#         db["inventory"].append(unit)
#         donor["last_donation_date"] = today.isoformat()
#         donor["donation_count"] += 1
#         save_db(db)
#     return jsonify(unit), 201
#
#
# @app.route("/api/inventory/<int:unit_id>/issue", methods=["POST"])
# def issue_unit(unit_id):
#     data = request.get_json(silent=True) or {}
#     hospital = str(data.get("hospital", "")).strip()
#     if len(hospital) < 3:
#         return err("Hospital name is required (min 3 characters).")
#     with LOCK:
#         db = load_db()
#         unit = next((u for u in db["inventory"] if u["id"] == unit_id), None)
#         if not unit:
#             return err("Blood unit not found", 404)
#         st = unit_status(unit)
#         if st == "Issued":
#             return err("This unit is already issued.", 409)
#         if st == "Expired":
#             return err("This unit has expired and cannot be issued.", 409)
#         unit["status"] = "Issued"
#         unit["issued_to"] = hospital
#         unit["issued_on"] = datetime.now().strftime("%Y-%m-%d %H:%M")
#         save_db(db)
#     return jsonify(unit)
#
#
# if __name__ == "__main__":
#     app.run(debug=True)
#
#
"""
Blood Bank Management System
Module 1: Donor Management
Module 2: Blood Inventory Management
Integration: a donation links a donor to a blood unit, updates donor history,
and updates stock.  Database: data.json (no SQL).
Run:  pip install flask  ->  python app.py  ->  open http://127.0.0.1:5000
"""
import json
import math
import os
import re
import tempfile
import threading
from datetime import date, datetime, timedelta

from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static")
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
LOCK = threading.Lock()

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
GENDERS = ["Male", "Female", "Other"]
MIN_AGE, MAX_AGE = 18, 65
MIN_WEIGHT = 50          # kg
MIN_HB, MAX_HB = 12.5, 20.0  # g/dL
DONATION_GAP_DAYS = 90   # days between two donations
SHELF_LIFE_DAYS = 35     # blood unit expiry
LOW_STOCK_LIMIT = 5      # units


# ---------------------------------------------------------------- JSON "database"
class DatabaseError(Exception):
    """Raised when data.json cannot be read (e.g. corrupted)."""


def load_db():
    if not os.path.exists(DB_FILE):
        return {"donors": [], "inventory": [], "next_donor_id": 1, "next_unit_id": 1}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        raise DatabaseError("Database file is unreadable or corrupted.")


def save_db(db):
    """Write to a temp file first, then replace, so a crash cannot corrupt data.json."""
    folder = os.path.dirname(DB_FILE)
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, allow_nan=False)
        os.replace(tmp, DB_FILE)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


@app.errorhandler(DatabaseError)
def handle_db_error(e):
    return jsonify({"error": str(e) + " Please restore or delete data.json and retry."}), 500


def err(msg, code=400, errors=None):
    body = {"error": msg}
    if errors:
        body["errors"] = errors
    return jsonify(body), code


# ---------------------------------------------------------------- validation
def to_whole_number(value):
    """int from a whole number or numeric string; rejects bool, decimals, NaN, inf."""
    if isinstance(value, bool):
        raise ValueError
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError
        return int(value)
    return int(value)


def to_finite_float(value):
    """float that must be a real, finite number (rejects 'nan', 'inf', bool)."""
    if isinstance(value, bool):
        raise ValueError
    number = float(value)
    if not math.isfinite(number):
        raise ValueError
    return number


def validate_donor(data, db, donor_id=None):
    """Return list of error strings (empty list = valid)."""
    errors = []

    name = str(data.get("name", "")).strip()
    if not name:
        errors.append("Name is required.")
    elif not (2 <= len(name) <= 50
              and re.fullmatch(r"[A-Za-z]+(?:[ .'-]+[A-Za-z]+)*\.?", name)):
        errors.append("Name must be 2-50 letters (no digits).")

    try:
        age = to_whole_number(data.get("age"))
        if age < MIN_AGE or age > MAX_AGE:
            errors.append(f"Age must be between {MIN_AGE} and {MAX_AGE}.")
    except (TypeError, ValueError):
        errors.append("Age must be a whole number.")

    if data.get("gender") not in GENDERS:
        errors.append("Gender must be Male, Female or Other.")

    if data.get("blood_group") not in BLOOD_GROUPS:
        errors.append("Invalid blood group.")

    try:
        weight = to_finite_float(data.get("weight"))
        if weight < MIN_WEIGHT:
            errors.append(f"Weight must be at least {MIN_WEIGHT} kg.")
        elif weight > 200:
            errors.append("Weight must be 200 kg or less.")
    except (TypeError, ValueError):
        errors.append("Weight must be a number.")

    try:
        hb = to_finite_float(data.get("hemoglobin"))
        if hb < MIN_HB or hb > MAX_HB:
            errors.append(f"Hemoglobin must be between {MIN_HB} and {MAX_HB} g/dL.")
    except (TypeError, ValueError):
        errors.append("Hemoglobin must be a number.")

    phone = str(data.get("phone", "")).strip()
    if not re.fullmatch(r"[6-9][0-9]{9}", phone):
        errors.append("Phone must be 10 digits and start with 6, 7, 8 or 9.")
    else:
        for d in db["donors"]:
            if d["phone"] == phone and d["id"] != donor_id:
                errors.append("A donor with this phone number already exists.")
                break

    email = str(data.get("email", "")).strip()
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errors.append("Email format is invalid.")

    return errors


def find_donor(db, donor_id):
    return next((d for d in db["donors"] if d["id"] == donor_id), None)


def unit_status(unit):
    if unit["status"] == "Issued":
        return "Issued"
    if date.fromisoformat(unit["expiry_date"]) < date.today():
        return "Expired"
    return "Available"


# ---------------------------------------------------------------- pages
@app.route("/")
def home():
    return send_from_directory("static", "index.html")


# ================================================================ MODULE 1: DONORS
@app.route("/api/donors", methods=["GET"])
def list_donors():
    db = load_db()
    donors = db["donors"]
    bg = request.args.get("blood_group")
    q = request.args.get("q", "").strip().lower()
    if bg:
        donors = [d for d in donors if d["blood_group"] == bg]
    if q:
        donors = [d for d in donors if q in d["name"].lower() or q in d["phone"]]
    return jsonify(donors)


@app.route("/api/donors", methods=["POST"])
def add_donor():
    data = request.get_json(silent=True) or {}
    with LOCK:
        db = load_db()
        errors = validate_donor(data, db)
        if errors:
            return err("Validation failed", 400, errors)
        donor = {
            "id": db["next_donor_id"],
            "name": data["name"].strip(),
            "age": int(data["age"]),
            "gender": data["gender"],
            "blood_group": data["blood_group"],
            "weight": float(data["weight"]),
            "hemoglobin": float(data["hemoglobin"]),
            "phone": str(data["phone"]).strip(),
            "email": str(data.get("email", "")).strip(),
            "registered_on": date.today().isoformat(),
            "last_donation_date": None,
            "donation_count": 0,
        }
        db["next_donor_id"] += 1
        db["donors"].append(donor)
        save_db(db)
    return jsonify(donor), 201


@app.route("/api/donors/<int:donor_id>", methods=["PUT"])
def update_donor(donor_id):
    data = request.get_json(silent=True) or {}
    with LOCK:
        db = load_db()
        donor = find_donor(db, donor_id)
        if not donor:
            return err("Donor not found", 404)
        errors = validate_donor(data, db, donor_id)
        if errors:
            return err("Validation failed", 400, errors)
        donor.update({
            "name": data["name"].strip(),
            "age": int(data["age"]),
            "gender": data["gender"],
            "blood_group": data["blood_group"],
            "weight": float(data["weight"]),
            "hemoglobin": float(data["hemoglobin"]),
            "phone": str(data["phone"]).strip(),
            "email": str(data.get("email", "")).strip(),
        })
        # keep the donor name on existing blood units in sync
        for u in db["inventory"]:
            if u["donor_id"] == donor_id:
                u["donor_name"] = donor["name"]
        save_db(db)
    return jsonify(donor)


@app.route("/api/donors/<int:donor_id>", methods=["DELETE"])
def delete_donor(donor_id):
    with LOCK:
        db = load_db()
        donor = find_donor(db, donor_id)
        if not donor:
            return err("Donor not found", 404)
        if any(u["donor_id"] == donor_id and unit_status(u) == "Available"
               for u in db["inventory"]):
            return err("Cannot delete: donor has blood units still in stock.", 409)
        if any(u["donor_id"] == donor_id for u in db["inventory"]):
            return err("Cannot delete: donor has donation records (issued or expired "
                       "units) that must be kept.", 409)
        db["donors"].remove(donor)
        save_db(db)
    return jsonify({"message": "Donor deleted"})


@app.route("/api/donors/<int:donor_id>/eligibility", methods=["GET"])
def eligibility(donor_id):
    db = load_db()
    donor = find_donor(db, donor_id)
    if not donor:
        return err("Donor not found", 404)
    ok, reason = check_eligible(donor)
    return jsonify({"eligible": ok, "reason": reason})


def check_eligible(donor):
    if donor["last_donation_date"]:
        last = date.fromisoformat(donor["last_donation_date"])
        next_ok = last + timedelta(days=DONATION_GAP_DAYS)
        if date.today() < next_ok:
            return False, f"Last donated on {last}. Eligible again on {next_ok}."
    return True, "Eligible to donate."


# ================================================================ MODULE 2: INVENTORY
@app.route("/api/inventory", methods=["GET"])
def list_inventory():
    db = load_db()
    units = []
    for u in db["inventory"]:
        row = dict(u)
        row["status"] = unit_status(u)
        units.append(row)
    bg = request.args.get("blood_group")
    st = request.args.get("status")
    if bg:
        units = [u for u in units if u["blood_group"] == bg]
    if st:
        units = [u for u in units if u["status"] == st]
    return jsonify(units)


@app.route("/api/inventory/summary", methods=["GET"])
def stock_summary():
    db = load_db()
    summary = {bg: 0 for bg in BLOOD_GROUPS}
    expiring_soon = []
    for u in db["inventory"]:
        if unit_status(u) == "Available":
            summary[u["blood_group"]] += 1
            days_left = (date.fromisoformat(u["expiry_date"]) - date.today()).days
            if days_left <= 7:
                expiring_soon.append({"unit_id": u["id"], "blood_group": u["blood_group"],
                                      "days_left": days_left})
    low = [bg for bg, n in summary.items() if n < LOW_STOCK_LIMIT]
    return jsonify({"stock": summary, "low_stock": low, "expiring_soon": expiring_soon,
                    "low_stock_limit": LOW_STOCK_LIMIT})


@app.route("/api/inventory", methods=["POST"])
def record_donation():
    """INTEGRATION POINT: donation -> checks donor (module 1) -> adds unit (module 2)
    -> updates donor history (module 1)."""
    data = request.get_json(silent=True) or {}
    try:
        donor_id = int(data.get("donor_id"))
    except (TypeError, ValueError):
        return err("donor_id is required and must be a number.")

    try:
        volume = to_whole_number(data.get("volume_ml", 350))
        if volume < 300 or volume > 500:
            return err("Volume must be between 300 and 500 ml.")
    except (TypeError, ValueError):
        return err("Volume must be a number.")

    with LOCK:
        db = load_db()
        donor = find_donor(db, donor_id)
        if not donor:
            return err("Donor not found", 404)
        ok, reason = check_eligible(donor)
        if not ok:
            return err(reason, 409)

        today = date.today()
        unit = {
            "id": db["next_unit_id"],
            "donor_id": donor_id,
            "donor_name": donor["name"],
            "blood_group": donor["blood_group"],
            "volume_ml": volume,
            "collection_date": today.isoformat(),
            "expiry_date": (today + timedelta(days=SHELF_LIFE_DAYS)).isoformat(),
            "status": "Available",
            "issued_to": None,
            "issued_on": None,
        }
        db["next_unit_id"] += 1
        db["inventory"].append(unit)
        donor["last_donation_date"] = today.isoformat()
        donor["donation_count"] += 1
        save_db(db)
    return jsonify(unit), 201


@app.route("/api/inventory/<int:unit_id>/issue", methods=["POST"])
def issue_unit(unit_id):
    data = request.get_json(silent=True) or {}
    hospital = str(data.get("hospital", "")).strip()
    if len(hospital) < 3:
        return err("Hospital name is required (min 3 characters).")
    with LOCK:
        db = load_db()
        unit = next((u for u in db["inventory"] if u["id"] == unit_id), None)
        if not unit:
            return err("Blood unit not found", 404)
        st = unit_status(unit)
        if st == "Issued":
            return err("This unit is already issued.", 409)
        if st == "Expired":
            return err("This unit has expired and cannot be issued.", 409)
        unit["status"] = "Issued"
        unit["issued_to"] = hospital
        unit["issued_on"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_db(db)
    return jsonify(unit)


if __name__ == "__main__":
    app.run(debug=True)
