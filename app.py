from __future__ import annotations

from typing import Any, Dict, Optional
import re

from fastapi import FastAPI
from pydantic import BaseModel


# ----------------- Normalizer helpers -----------------

EMPTY_STRINGS = {"", " ", "null", "none", "n/a", "na", "undefined"}

def is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip().lower() in EMPTY_STRINGS
    if isinstance(v, (list, tuple, set, dict)):
        return len(v) == 0
    return False

def norm_phone(phone: Any) -> Optional[str]:
    if is_empty(phone):
        return None
    s = str(phone).strip()
    s = re.sub(r"[^\d+]", "", s)
    if s.startswith("00"):
        s = "+" + s[2:]
    digits = re.sub(r"\D", "", s)
    if s.startswith("0") and len(digits) == 10:
        return "+33" + digits[1:]
    return s if s.startswith("+") else s

def norm_email(email: Any) -> Optional[str]:
    if is_empty(email):
        return None
    s = str(email).strip().lower()
    return s if "@" in s else None

def as_int(v: Any) -> Optional[int]:
    if is_empty(v):
        return None
    try:
        return int(float(str(v).replace(",", ".")))
    except Exception:
        return None

def option_id_to_text(field: Dict[str, Any], option_id: str) -> Optional[str]:
    for opt in field.get("options") or []:
        if opt.get("id") == option_id:
            return opt.get("text")
    return None

def decode_field_value(field: Dict[str, Any]) -> Any:
    v = field.get("value")
    ftype = field.get("type")

    if ftype == "MULTIPLE_CHOICE":
        if v is None:
            return None
        if isinstance(v, list):
            texts = []
            for oid in v:
                t = option_id_to_text(field, oid)
                texts.append(t if t is not None else oid)
            return texts
        if isinstance(v, str):
            t = option_id_to_text(field, v)
            return t if t is not None else v

    return v

def build_answers(bundle_item: Dict[str, Any]) -> Dict[str, Any]:
    data = bundle_item.get("data") or {}
    fields = data.get("fields") or []

    answers: Dict[str, Any] = {}
    meta = {
        "responseId": data.get("responseId"),
        "submissionId": data.get("submissionId"),
        "respondentId": data.get("respondentId"),
        "formId": data.get("formId"),
        "formName": data.get("formName"),
        "createdAt": data.get("createdAt"),
    }
    answers["_meta"] = meta

    for f in fields:
        key = f.get("key")
        if not key:
            continue
        answers[key] = {
            "label": f.get("label"),
            "type": f.get("type"),
            "value": decode_field_value(f),
        }

    return answers

def get_value(answers: Dict[str, Any], key: str) -> Any:
    node = answers.get(key)
    if not isinstance(node, dict):
        return None
    return node.get("value")

def build_canonical(answers: Dict[str, Any]) -> Dict[str, Any]:
    # ⚠️ Garde TES clés ici (elles doivent correspondre à ton bundle réel Tally/Make)
    role = get_value(answers, "question_OzXkVA_7be398b7-7e42-4736-b35e-b9a78d556f22")
    city_project = get_value(answers, "question_V0PDxl")
    first_name = get_value(answers, "question_EXlMAL")
    last_name = get_value(answers, "question_r6OvgL")
    phone = get_value(answers, "question_487zEo")
    email = get_value(answers, "question_jyovg9")

    price_net_seller = as_int(get_value(answers, "question_EXlMaL"))
    budget_max = as_int(get_value(answers, "question_P69kP0"))

    property_type = get_value(answers, "question_WNEKXe")
    surface = as_int(get_value(answers, "question_9WZMr4"))
    land_surface = as_int(get_value(answers, "question_e6rvoo"))
    rooms = as_int(get_value(answers, "question_WNR1ZQ"))

    return {
        "role": None if is_empty(role) else str(role).strip(),
        "city_project": None if is_empty(city_project) else str(city_project).strip(),
        "first_name": None if is_empty(first_name) else str(first_name).strip(),
        "last_name": None if is_empty(last_name) else str(last_name).strip(),
        "phone": norm_phone(phone),
        "email": norm_email(email),
        "price_net_seller": price_net_seller,
        "budget_max": budget_max,
        "property_type": property_type,
        "surface_m2": surface,
        "land_surface_m2": land_surface,
        "bedrooms": rooms,
    }

def drop_empty(d: Dict[str, Any]) -> Dict[str, Any]:
    """Enlève les champs vides pour éviter d'envoyer du null à Supabase."""
    return {k: v for k, v in d.items() if not is_empty(v)}


# ----------------- FastAPI -----------------

app = FastAPI()

class Payload(BaseModel):
    raw: Dict[str, Any]

@app.post("/normalize")
def normalize(payload: Payload):
    """
    Attend raw = le bundle (ou au minimum un objet qui contient data.fields)
    Retourne canonical "propre" (sans champs vides)
    """
    answers = build_answers(payload.raw)
    canonical = build_canonical(answers)
    return {
        "canonical": drop_empty(canonical),
        "meta": answers.get("_meta", {}),
    }
}
