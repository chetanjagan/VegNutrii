"""Meal catalogue. Each meal is a list of (component_key, servings).

Nutrition, cost, diet tags and grocery needs are all derived from the
components, so they can never drift out of sync.

cuisine "any" means the meal suits every regional preference (fitness staples,
pan-Indian dishes). The planner prefers the user's cuisine but can use these.
"""
from .foods import COMPONENTS

B, L, S, D = "breakfast", "lunch", "snack", "dinner"
LD = (L, D)

_RAW = [
    # key, name, slots, cuisine, minutes, components
    # ── North Indian ─────────────────────────────────────────────────────
    ("moong_chilla_curd", "Moong dal chilla, green chutney and curd", (B,), "north_indian", 20, [("moong_chilla", 1), ("green_chutney", 1), ("curd", 0.5)]),
    ("paneer_paratha_curd", "Paneer paratha (2) with curd", (B,), "north_indian", 25, [("paneer_paratha", 2), ("curd", 0.5)]),
    ("besan_cheela_chutney", "Besan cheela with green chutney", (B,), "north_indian", 15, [("besan_cheela", 1), ("green_chutney", 1), ("buttermilk", 1)]),
    ("aloo_paratha_curd", "Aloo paratha (2) with curd", (B,), "north_indian", 25, [("aloo_paratha", 2), ("curd", 0.5)]),
    ("egg_bhurji_roti", "Egg bhurji with 2 rotis", (B, D), "north_indian", 15, [("egg_bhurji", 1), ("roti", 2)]),
    ("sattu_banana_peanuts", "Sattu sharbat, banana and roasted peanuts", (B,), "north_indian", 5, [("sattu_drink", 1), ("banana", 1), ("peanuts", 1)]),
    ("dal_tadka_thali", "Dal tadka, 2 rotis, mixed veg and salad", LD, "north_indian", 30, [("dal_tadka", 1), ("roti", 2), ("mixed_veg", 1), ("salad", 1)]),
    ("rajma_chawal", "Rajma chawal with raita", LD, "north_indian", 35, [("rajma", 1), ("rice_white", 1), ("raita", 0.5)]),
    ("chole_roti", "Chole with 2 rotis and salad", LD, "north_indian", 30, [("chole", 1), ("roti", 2), ("salad", 1)]),
    ("palak_paneer_roti", "Palak paneer, 2 rotis and moong dal", LD, "north_indian", 35, [("palak_paneer", 1), ("roti", 2), ("moong_dal", 0.5)]),
    ("pbm_roti", "Paneer butter masala, 2 rotis and salad", (L,), "north_indian", 30, [("paneer_butter_masala", 1), ("roti", 2), ("salad", 1)]),
    ("kala_chana_rice", "Kala chana, jeera rice and raita", (L,), "north_indian", 30, [("kala_chana", 1), ("jeera_rice", 1), ("raita", 0.5)]),
    ("matar_paneer_roti", "Matar paneer with 2 rotis and salad", LD, "north_indian", 30, [("matar_paneer", 1), ("roti", 2), ("salad", 1)]),
    ("jain_thali", "Plain toor dal, 2 rotis, lauki and curd", LD, "north_indian", 30, [("dal_jain", 1), ("roti", 2), ("lauki_sabzi", 1), ("curd", 0.5)]),
    ("jain_chole_rice", "Chole (no onion-garlic) with rice and salad", LD, "north_indian", 30, [("chole_jain", 1), ("rice_white", 1), ("salad", 1)]),
    ("khichdi_curd", "Moong dal khichdi with curd", (D,), "north_indian", 25, [("dal_khichdi", 1), ("curd", 0.5)]),
    ("dal_makhani_roti", "Dal makhani, 2 rotis and salad", (D,), "north_indian", 30, [("dal_makhani", 1), ("roti", 2), ("salad", 1)]),
    ("paneer_bhurji_roti", "Paneer bhurji with 2 rotis and salad", (D, B), "north_indian", 20, [("paneer_bhurji", 1), ("roti", 2), ("salad", 1)]),
    ("chole_brown_rice", "Chana masala with brown rice", (D,), "north_indian", 30, [("chole", 1), ("rice_brown", 1)]),
    ("moong_dal_bhindi", "Moong dal, 2 rotis and bhindi", (D,), "north_indian", 25, [("moong_dal", 1), ("roti", 2), ("bhindi", 1)]),
    ("aloo_gobi_dal", "Aloo gobi, dal and 2 rotis", (D,), "north_indian", 30, [("aloo_gobi", 1), ("dal_jain", 0.5), ("roti", 2)]),
    ("jain_paneer_roti", "Paneer capsicum tomato with 2 rotis and dal", LD, "north_indian", 25, [("paneer_jain", 1), ("roti", 2), ("dal_jain", 0.5)]),
    ("masoor_rice", "Masoor dal, rice and salad", (D,), "north_indian", 25, [("masoor_dal", 1), ("rice_white", 1), ("salad", 1)]),

    # ── South Indian ─────────────────────────────────────────────────────
    ("idli_sambar", "Idli (3), sambar and coconut chutney", (B, D), "south_indian", 15, [("idli", 1.5), ("sambar", 1), ("coconut_chutney", 1)]),
    ("masala_dosa_sambar", "Masala dosa with sambar and chutney", (B, D), "south_indian", 20, [("masala_dosa", 1), ("sambar", 1), ("coconut_chutney", 1)]),
    ("pesarattu_chutney", "Pesarattu (2) with coconut chutney", (B,), "south_indian", 20, [("pesarattu", 1), ("coconut_chutney", 1)]),
    ("pongal_sambar", "Ven pongal with sambar", (B,), "south_indian", 25, [("ven_pongal", 1), ("sambar", 0.5)]),
    ("rava_idli_sambar", "Rava idli (3) with sambar", (B,), "south_indian", 15, [("rava_idli", 1), ("sambar", 0.5)]),
    ("dosa_peanut_chutney", "Plain dosa (2), peanut chutney and sambar", (B, D), "south_indian", 15, [("dosa_plain", 2), ("peanut_chutney", 1), ("sambar", 0.5)]),
    ("uttapam_chutney", "Onion uttapam (2) with chutney", (B, D), "south_indian", 20, [("uttapam", 1), ("coconut_chutney", 1)]),
    ("upma_curd", "Rava upma with curd", (B,), "south_indian", 15, [("rava_upma", 1), ("curd", 0.5)]),
    ("ragi_malt_almonds", "Ragi malt with almonds and banana", (B,), "south_indian", 10, [("ragi_malt", 1), ("almonds", 1), ("banana", 1)]),
    ("sambar_rice_meals", "Sambar rice, rasam, beans poriyal and curd", (L,), "south_indian", 30, [("sambar", 1), ("rice_white", 1), ("rasam", 0.5), ("beans_poriyal", 1), ("curd", 0.5)]),
    ("bisi_bele_raita", "Bisi bele bath with raita", (L,), "south_indian", 35, [("bisi_bele_bath", 1), ("raita", 0.5)]),
    ("curd_rice_sundal", "Curd rice with chickpea sundal", (L,), "south_indian", 15, [("curd", 1), ("rice_white", 1), ("sundal", 0.5)]),
    ("rasam_kootu", "Rasam rice, kootu and papad", LD, "south_indian", 25, [("rasam", 1), ("rice_white", 1), ("kootu", 1), ("papad", 1)]),
    ("ragi_mudde_sambar", "Ragi mudde, sambar and palya", LD, "south_indian", 30, [("ragi_mudde", 1), ("sambar", 1), ("cabbage_poriyal", 1)]),
    ("avial_rice", "Avial, rice and moong dal", (L,), "south_indian", 35, [("avial", 1), ("rice_white", 1), ("moong_dal", 0.5)]),
    ("chapati_kootu", "2 chapatis, moong dal and cabbage poriyal", (D,), "south_indian", 25, [("roti", 2), ("moong_dal", 1), ("cabbage_poriyal", 1)]),
    ("appam_stew", "Appam (2) with vegetable stew", (D, B), "south_indian", 25, [("appam", 1), ("veg_stew", 1)]),
    ("idiyappam_stew", "Idiyappam with stew and sundal", (D,), "south_indian", 20, [("idiyappam", 1), ("veg_stew", 1), ("sundal", 0.5)]),

    # ── Gujarati ─────────────────────────────────────────────────────────
    ("thepla_curd", "Methi thepla with curd", (B, D), "gujarati", 20, [("methi_thepla", 1), ("curd", 0.5)]),
    ("dhokla_chutney", "Khaman dhokla with green chutney", (B, S), "gujarati", 25, [("dhokla", 1.5), ("green_chutney", 1)]),
    ("handvo_curd", "Handvo with curd", (B, D), "gujarati", 30, [("handvo", 1.5), ("curd", 0.5)]),
    ("khakhra_chai", "Khakhra, masala chai and roasted chana", (B, S), "gujarati", 5, [("khakhra", 1), ("masala_chai", 1), ("roasted_chana", 0.5)]),
    ("gujarati_thali", "Gujarati dal, rotli, bhaat and shaak", (L,), "gujarati", 30, [("dal_jain", 1), ("roti", 2), ("rice_white", 0.5), ("lauki_sabzi", 1)]),
    ("kadhi_khichdi", "Kadhi khichdi", LD, "gujarati", 30, [("kadhi", 1), ("dal_khichdi", 1)]),
    ("dal_dhokli_salad", "Dal dhokli with salad", LD, "gujarati", 35, [("dal_dhokli", 1), ("salad", 1)]),
    ("undhiyu_rotli", "Undhiyu, 2 rotlis and curd", (L,), "gujarati", 40, [("undhiyu", 1), ("roti", 2), ("curd", 0.5)]),
    ("rotla_kadhi", "Bajra rotla, kadhi and lauki", LD, "gujarati", 30, [("bajra_rotla", 2), ("kadhi", 1), ("lauki_sabzi", 1)]),

    # ── Maharashtrian ───────────────────────────────────────────────────
    ("kanda_poha_chai", "Kanda poha with masala chai", (B,), "maharashtrian", 15, [("poha", 1), ("masala_chai", 1)]),
    ("misal_pav", "Misal pav", (B, L), "maharashtrian", 30, [("misal", 1)]),
    ("thalipeeth_curd", "Thalipeeth (2) with curd", (B, D), "maharashtrian", 20, [("thalipeeth", 1), ("curd", 0.5)]),
    ("bhakri_masoor", "Jowar bhakri, masoor usal and salad", LD, "maharashtrian", 30, [("jowar_bhakri", 2), ("masoor_dal", 1), ("salad", 1)]),
    ("varan_bhaat", "Varan bhaat with bhindi", LD, "maharashtrian", 25, [("dal_jain", 1), ("rice_white", 1), ("bhindi", 1)]),
    ("usal_chapati", "Sprouts usal, 2 chapatis and chaas", LD, "maharashtrian", 25, [("sprouts_usal", 1), ("roti", 2), ("buttermilk", 1)]),

    # ── Bengali ──────────────────────────────────────────────────────────
    ("cholar_dal_rice", "Cholar dal, rice and beans", (L,), "bengali", 30, [("cholar_dal", 1), ("rice_white", 1), ("beans_poriyal", 1)]),
    ("bengali_moong_rice", "Moong dal, rice and mixed veg", LD, "bengali", 25, [("moong_dal", 1), ("rice_white", 1), ("mixed_veg", 1)]),
    ("bengali_dal_roti", "Masoor dal, 2 rotis and aloo gobi", (D,), "bengali", 30, [("masoor_dal", 1), ("roti", 2), ("aloo_gobi", 0.7)]),

    # ── Regional depth: high-protein and Jain/sattvic-friendly options ──
    ("idli_sundal", "Idli (3), sambar and chickpea sundal", (B,), "south_indian", 20, [("idli", 1.5), ("sambar", 1), ("sundal", 0.5)]),
    ("pesarattu_curd", "Pesarattu (2) with peanut chutney and curd", (B, D), "south_indian", 20, [("pesarattu", 1), ("peanut_chutney", 1), ("curd", 0.5)]),
    ("idli_moong_jain", "Idli (3), moong dal and coconut chutney", (B, D), "south_indian", 20, [("idli", 1.5), ("moong_dal", 1), ("coconut_chutney", 1)]),
    ("south_jain_meals", "Rice, plain dal, beans poriyal and curd", LD, "south_indian", 25, [("rice_white", 1), ("dal_jain", 1), ("beans_poriyal", 1), ("curd", 0.5)]),
    ("rice_sambar_sundal", "Rice, sambar, sundal and curd", (L,), "south_indian", 25, [("rice_white", 1), ("sambar", 1), ("sundal", 0.5), ("curd", 0.5)]),
    ("chapati_sundal_kootu", "2 chapatis, kootu and sundal", (D,), "south_indian", 25, [("roti", 2), ("kootu", 1), ("sundal", 0.5)]),
    ("ragi_soya_saaru", "Ragi mudde, soya saaru and palya", LD, "south_indian", 30, [("ragi_mudde", 1), ("soya_curry", 1), ("cabbage_poriyal", 1)]),
    ("curd_rice_moong", "Curd rice, moong dal and beans poriyal", LD, "south_indian", 20, [("curd", 1), ("rice_white", 1), ("moong_dal", 0.5), ("beans_poriyal", 1)]),
    ("appam_egg_curry", "Appam (2) with egg curry", (D,), "south_indian", 25, [("appam", 1), ("egg_curry", 1)]),
    ("dhokla_curd", "Khaman dhokla with curd", (B,), "gujarati", 25, [("dhokla", 1.5), ("curd", 1)]),
    ("guj_paneer_thali", "Moong dal, 2 rotlis and paneer shaak", LD, "gujarati", 30, [("moong_dal", 1), ("roti", 2), ("paneer_jain", 1)]),
    ("kadhi_rice_moong", "Kadhi, rice and moong dal", (L,), "gujarati", 30, [("kadhi", 1), ("rice_white", 1), ("moong_dal", 0.5)]),
    ("rotla_paneer_chaas", "Bajra rotla, paneer shaak and chaas", LD, "gujarati", 30, [("bajra_rotla", 2), ("paneer_jain", 1), ("buttermilk", 1)]),
    ("khichdi_paneer_shaak", "Khichdi with paneer shaak", (D,), "gujarati", 30, [("dal_khichdi", 1), ("paneer_jain", 0.7)]),
    ("thepla_chana", "Methi thepla, curd and roasted chana", (B,), "gujarati", 20, [("methi_thepla", 1), ("curd", 0.5), ("roasted_chana", 0.5)]),
    ("varan_bhaat_lauki", "Varan bhaat with lauki bhaji", LD, "maharashtrian", 25, [("dal_jain", 1), ("rice_white", 1), ("lauki_sabzi", 1)]),
    ("bhakri_varan_paneer", "Jowar bhakri, varan and paneer bhaji", LD, "maharashtrian", 30, [("jowar_bhakri", 2), ("dal_jain", 1), ("paneer_jain", 0.7)]),
    ("dadpe_poha_curd", "Dadpe poha with curd", (B,), "maharashtrian", 15, [("poha_plain", 1), ("curd", 0.75)]),
    ("bhakri_curd_chutney", "Jowar bhakri, curd and peanut chutney", (B, D), "maharashtrian", 15, [("jowar_bhakri", 2), ("curd", 0.75), ("peanut_chutney", 1)]),
    ("bhakri_soya_maha", "Jowar bhakri with soya bhaji", LD, "maharashtrian", 25, [("jowar_bhakri", 2), ("soya_jain", 1), ("salad", 1)]),
    ("chire_doi", "Chire with curd and banana", (B,), "bengali", 5, [("poha_plain", 1), ("curd", 0.75), ("banana", 1)]),
    ("khichuri_doi", "Moong dal khichuri with curd", LD, "bengali", 25, [("dal_khichdi", 1), ("curd", 0.5)]),
    ("chhanar_dalna_rice", "Chhanar dalna (paneer curry) with rice", LD, "bengali", 30, [("matar_paneer", 1), ("rice_white", 1)]),
    ("cholar_dal_roti", "Cholar dal with 2 rotis and salad", (D, L), "bengali", 25, [("cholar_dal", 1), ("roti", 2), ("salad", 1)]),
    ("bengali_egg_rice", "Dimer jhol (egg curry) with rice", LD, "bengali", 30, [("egg_curry", 1), ("rice_white", 1)]),

    # ── Pan-Indian / fitness staples ────────────────────────────────────
    ("oats_banana", "Oats in milk with banana", (B,), "any", 10, [("oats_porridge", 1), ("banana", 1)]),
    ("oats_pb", "Oats in milk with banana and peanut butter", (B,), "any", 10, [("oats_porridge", 1), ("banana", 1), ("peanut_butter", 0.5)]),
    ("masala_oats_eggs", "Masala oats with 2 boiled eggs", (B,), "any", 15, [("oats_savory", 1), ("boiled_eggs", 1)]),
    ("tofu_bhurji_roti", "Tofu bhurji with 2 rotis", (B, D), "any", 15, [("tofu_bhurji", 1), ("roti", 2)]),
    ("pb_smoothie", "Banana peanut butter smoothie", (B, S), "any", 5, [("smoothie_pb", 1)]),
    ("yogurt_bowl", "Greek yogurt with fruit and chia", (B, S), "any", 5, [("greek_yogurt", 1), ("fruit", 1), ("chia", 1)]),
    ("soy_milk_oats", "Oats with soy milk, banana and flax", (B,), "any", 10, [("oats_plain", 1), ("soy_milk", 1), ("banana", 1), ("flax", 1), ("peanut_butter", 0.5)]),
    ("soya_roti", "Soya chunks curry, 2 rotis and salad", LD, "any", 25, [("soya_curry", 1), ("roti", 2), ("salad", 1)]),
    ("soya_jain_rice", "Soya chunks in tomato gravy with rice", LD, "any", 25, [("soya_jain", 1), ("rice_white", 1), ("salad", 1)]),
    ("egg_curry_rice", "Egg curry with rice and salad", LD, "any", 30, [("egg_curry", 1), ("rice_white", 1), ("salad", 1)]),
    ("quinoa_chole_bowl", "Quinoa and chickpea bowl", LD, "any", 25, [("quinoa", 1), ("chole_jain", 1), ("salad", 1)]),
    ("tofu_quinoa", "Tofu stir-fry with quinoa", LD, "any", 25, [("tofu_stirfry", 1), ("quinoa", 1)]),
    ("paneer_tikka_salad", "Paneer tikka, 2 rotis and salad", LD, "any", 30, [("paneer_tikka", 1), ("roti", 2), ("salad", 1)]),

    # ── Fasting (vrat) ──────────────────────────────────────────────────
    ("sabudana_curd", "Sabudana khichdi with curd", (B, L, D), "any", 20, [("sabudana_khichdi", 1), ("curd", 0.5)]),
    ("kuttu_cheela_curd", "Kuttu cheela with curd", (B, D), "any", 15, [("kuttu_cheela", 1), ("curd", 0.5)]),
    ("rajgira_paratha_raita", "Rajgira paratha with raita", (B, L, D), "any", 20, [("rajgira_paratha", 1), ("raita", 1)]),
    ("vrat_milk_fruit", "Milk, fruit and makhana", (B, S), "any", 5, [("milk", 1), ("fruit", 1), ("makhana", 0.5)]),
    ("samak_aloo_curd", "Samak rice, jeera aloo and curd", (L, D), "any", 25, [("samak_rice", 1), ("aloo_vrat", 1), ("curd", 0.5)]),
    ("kuttu_paneer", "Kuttu cheela with paneer and lauki", (L, D), "any", 25, [("kuttu_cheela", 1), ("paneer_cubes", 0.7), ("lauki_sabzi", 1)]),

    # ── Snacks ──────────────────────────────────────────────────────────
    ("chana_chai", "Roasted chana with masala chai", (S,), "any", 5, [("roasted_chana", 1), ("masala_chai", 1)]),
    ("pb_banana", "Banana with peanut butter", (S,), "any", 5, [("banana", 1), ("peanut_butter", 0.5)]),
    ("sprouts_chaat_snack", "Sprouts chaat", (S,), "any", 10, [("sprouts_chaat", 1)]),
    ("yogurt_almonds", "Greek yogurt with almonds", (S,), "any", 5, [("greek_yogurt", 1), ("almonds", 1)]),
    ("makhana_chai", "Roasted makhana with chai", (S,), "any", 5, [("makhana", 1), ("masala_chai", 1)]),
    ("paneer_snack", "Paneer cubes with pepper", (S,), "any", 5, [("paneer_cubes", 0.7)]),
    ("chaas_chikki", "Chaas with peanut chikki", (S,), "gujarati", 5, [("buttermilk", 1), ("chikki", 1)]),
    ("sundal_chai", "Sundal with chai", (S,), "south_indian", 10, [("sundal", 1), ("masala_chai", 1)]),
    ("curd_fruit", "Curd with fruit", (S,), "any", 5, [("curd", 0.75), ("fruit", 1)]),
    ("sattu_snack", "Sattu sharbat", (S,), "north_indian", 5, [("sattu_drink", 1)]),
    ("eggs_snack", "2 boiled eggs", (S,), "any", 10, [("boiled_eggs", 1)]),
    ("soymilk_almonds", "Soy milk with almonds", (S,), "any", 2, [("soy_milk", 1), ("almonds", 1)]),
    ("peanuts_apple", "Roasted peanuts with an apple", (S,), "any", 2, [("peanuts", 1), ("apple", 1)]),
    ("seeds_fruit", "Fruit with pumpkin seeds", (S,), "any", 2, [("fruit", 1), ("pumpkin_seeds", 1)]),
    ("milk_chikki", "Milk with peanut chikki", (S,), "any", 2, [("milk", 1), ("chikki", 1)]),
]

NUTRIENTS = ("kcal", "protein", "carbs", "fat", "fiber", "iron", "calcium", "b12", "zinc", "cost")


def _build(row):
    key, name, slots, cuisine, mins, parts = row
    totals = {n: 0.0 for n in NUTRIENTS}
    tags = set()
    fasting_ok = True
    for ckey, qty in parts:
        comp = COMPONENTS[ckey]
        for n in NUTRIENTS:
            totals[n] += comp[n] * qty
        tags |= comp["tags"] - {"fasting"}
        if "fasting" not in comp["tags"]:
            fasting_ok = False
    if fasting_ok:
        tags.add("fasting")
    return {
        "key": key, "name": name, "slots": slots, "cuisine": cuisine, "mins": mins,
        "parts": parts, "tags": tags,
        **{n: round(v, 1) for n, v in totals.items()},
    }


MEALS = {row[0]: _build(row) for row in _RAW}

CUISINES = {
    "north_indian": "North Indian",
    "south_indian": "South Indian",
    "gujarati": "Gujarati",
    "maharashtrian": "Maharashtrian",
    "bengali": "Bengali",
}
