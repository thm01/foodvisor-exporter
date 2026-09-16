#!/usr/bin/env python3
"""Fusion sans perte des réponses JSON d'un export Foodvisor."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def referenced_foods(value):
    ids = set()
    if isinstance(value, dict):
        if isinstance(value.get("food_id"), str):
            ids.add(value["food_id"])
        for item in value.values():
            ids.update(referenced_foods(item))
    elif isinstance(value, list):
        for item in value:
            ids.update(referenced_foods(item))
    return ids


def merge(source, output):
    manifest = read(source / "manifest.json")
    if read(source / "termine.json").get("complete") is not True:
        raise ValueError("L'export source n'est pas terminé.")
    start, end = manifest["start"], manifest["end"]
    collections = {}
    duplicates = {}
    excluded = {}
    files = sorted(source.glob("journal-*.json")) + sorted(source.glob("aliments-*.json"))
    for file in files:
        for key, values in read(file).items():
            if not isinstance(values, list):
                raise ValueError(f"Champ inattendu à préserver manuellement : {file.name}/{key}")
            records = collections.setdefault(key, {})
            for value in values:
                date = value.get("meal_date") if key == "macro_meals" else value.get("date")
                if date and not start <= date[:10] <= end:
                    excluded[key] = excluded.get(key, 0) + 1
                    continue
                if key == "macro_meals":
                    identity = (value["meal_date"], value["meal_type"])
                elif key == "food_info":
                    identity = value["food_id"]
                else:
                    identity = canonical(value)
                if identity in records:
                    if records[identity] != value:
                        raise ValueError(f"Versions contradictoires dans {key} : {identity}")
                    duplicates[key] = duplicates.get(key, 0) + 1
                else:
                    records[identity] = value
    meals = sorted(collections.pop("macro_meals", {}).values(), key=lambda v: (
        v["meal_date"], {"breakfast": 0, "lunch": 1, "snack": 2, "dinner": 3}.get(v["meal_type"], 4), v["meal_type"]))
    foods = collections.pop("food_info", {})
    missing = referenced_foods(meals) - foods.keys()
    if missing:
        raise ValueError(f"{len(missing)} fiches alimentaires manquantes.")
    days = {meal["meal_date"] for meal in meals}
    first, last = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    absent = [str(first + dt.timedelta(days=i)) for i in range((last - first).days + 1)
              if str(first + dt.timedelta(days=i)) not in days]
    document = {
        "metadata": {
            "format": "foodvisor-merged-export", "format_version": 1,
            "start": start, "end": end, "complete": True,
            "source_files": [f.name for f in files],
            "meal_count": len(meals), "food_count": len(foods),
            "days_with_meals": len(days), "days_without_meals": absent,
            "identical_duplicates_removed": duplicates,
            "records_outside_period_excluded": excluded,
            "notes": [
                "Valeurs d'origine conservées ; aucune conversion des quantités ou nutriments.",
                "Les main_food.food_id des repas renvoient aux clés de food_info_by_id.",
                "Ne pas interpréter directement quantity comme un nombre d'unités : conserver aussi serving_amount et unit_id.",
                "Les champs proteins_100g, carbs_100g, lipids_100g et fibers_100g utilisent les valeurs énergétiques Foodvisor, pas directement des grammes.",
                "Les coefficients utilisés pour convertir ces quatre champs en grammes sont respectivement 4, 4, 9 et 2.",
                "Les dates modified_at sont des dates de modification, pas nécessairement les heures des repas.",
                "Les URL d'images sont conservées ; les images elles-mêmes ne sont pas téléchargées.",
            ],
        },
        "macro_meals": meals,
        "food_info_by_id": dict(sorted(foods.items())),
    }
    for key, values in sorted(collections.items()):
        document[key] = sorted(values.values(), key=lambda v: (v.get("date", ""), canonical(v)))
    os.umask(0o077)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    assert read(output) == document
    print(json.dumps({"output": str(output), "meals": len(meals), "foods": len(foods),
                      "other_records": {k: len(v) for k, v in collections.items()},
                      "duplicates_removed": duplicates}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    merge(args.source, args.output)
