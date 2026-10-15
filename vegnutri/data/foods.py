"""Food components: the building blocks of every meal.

Each component is one serving of a dish or food as an Indian household would
serve it. Values are APPROXIMATE, compiled from IFCT 2017 (NIN) and USDA
FoodData Central style references, and rounded. Before a commercial launch,
have a registered dietitian verify these against IFCT 2017.

Columns:
  key, name, serving,
  kcal, protein g, carbs g, fat g, fibre g,
  iron mg, calcium mg, vitamin B12 mcg, zinc mg,
  cost INR (rough 2026 retail, per serving),
  tags (space-separated), grocery {item: grams | ml | pcs}

Tags:
  dairy, egg, soy, gluten, peanut, nuts, sesame, coconut, honey, mushroom
  onion_garlic  contains onion or garlic
  root          root/underground vegetable (excluded by Jain diets)
  fasting       acceptable during common vrat (Navratri, Ekadashi)
"""

_RAW = [
    # ── Breads and grains ────────────────────────────────────────────────
    ("roti", "Roti / chapati", "1 piece", 85, 3, 15, 0.5, 2.5, 1.0, 10, 0, 0.6, 3, "gluten", {"Whole wheat atta": 30}),
    ("paneer_paratha", "Paneer paratha", "1 piece", 280, 12, 28, 13, 3, 1.5, 180, 0.2, 1.2, 25, "dairy gluten", {"Whole wheat atta": 45, "Paneer": 50, "Cooking oil / ghee": 8}),
    ("aloo_paratha", "Aloo paratha", "1 piece", 260, 6, 38, 9, 4, 1.8, 25, 0, 0.9, 12, "gluten root", {"Whole wheat atta": 50, "Potatoes": 80, "Cooking oil / ghee": 8}),
    ("methi_thepla", "Methi thepla", "2 pieces", 240, 7, 32, 9, 5, 2.5, 80, 0, 1.0, 10, "gluten", {"Whole wheat atta": 50, "Besan": 10, "Methi leaves": 30, "Cooking oil / ghee": 8}),
    ("jowar_bhakri", "Jowar bhakri", "1 piece", 150, 4.5, 30, 2, 4, 1.8, 12, 0, 0.8, 4, "", {"Jowar flour": 45}),
    ("bajra_rotla", "Bajra rotla", "1 piece", 170, 5, 30, 3.5, 5, 3.5, 20, 0, 1.4, 4, "", {"Bajra flour": 50}),
    ("ragi_mudde", "Ragi mudde", "1 ball", 210, 4.5, 43, 0.8, 7, 2.4, 206, 0, 1.4, 5, "", {"Ragi flour": 60}),
    ("rice_white", "Steamed rice", "1 cup cooked", 205, 4.2, 45, 0.4, 0.6, 0.4, 16, 0, 0.8, 6, "", {"Rice": 65}),
    ("rice_brown", "Brown rice", "1 cup cooked", 216, 5, 45, 1.8, 3.5, 0.8, 20, 0, 1.2, 9, "", {"Brown rice": 65}),
    ("jeera_rice", "Jeera rice", "1 cup", 250, 4.5, 46, 5, 1, 0.8, 20, 0, 0.8, 8, "dairy", {"Rice": 65, "Cooking oil / ghee": 5}),
    ("quinoa", "Quinoa", "1 cup cooked", 222, 8, 39, 3.6, 5, 2.8, 31, 0, 2.0, 35, "", {"Quinoa": 60}),
    ("samak_rice", "Samak (barnyard millet) rice", "1 cup cooked", 180, 4, 38, 1.5, 4, 2.7, 12, 0, 1.5, 10, "fasting", {"Samak rice": 55}),
    ("pav", "Pav", "2 pieces", 240, 8, 46, 3, 2, 2.0, 40, 0, 0.6, 10, "gluten", {"Pav (pcs)": 2}),

    # ── Breakfast dishes ────────────────────────────────────────────────
    ("idli", "Idli", "2 pieces", 130, 4, 27, 0.4, 1.5, 0.8, 10, 0, 0.6, 8, "", {"Idli rice": 40, "Urad dal": 15}),
    ("dosa_plain", "Plain dosa", "1 piece", 170, 4, 28, 4.5, 1, 0.8, 10, 0, 0.6, 10, "", {"Idli rice": 45, "Urad dal": 12, "Cooking oil / ghee": 5}),
    ("masala_dosa", "Masala dosa", "1 piece", 300, 6, 45, 10, 3, 1.5, 25, 0, 0.9, 25, "root onion_garlic", {"Idli rice": 45, "Urad dal": 12, "Potatoes": 100, "Onions": 30, "Cooking oil / ghee": 8}),
    ("pesarattu", "Pesarattu (green moong dosa)", "2 pieces", 260, 15, 36, 6, 6, 3.0, 50, 0, 1.6, 12, "", {"Whole green moong": 70, "Cooking oil / ghee": 5}),
    ("uttapam", "Onion uttapam", "2 pieces", 330, 9, 52, 9, 3, 1.6, 30, 0, 1.0, 15, "onion_garlic", {"Idli rice": 60, "Urad dal": 15, "Onions": 30, "Cooking oil / ghee": 8}),
    ("rava_idli", "Rava idli", "3 pieces", 270, 8, 40, 8, 1.5, 1.2, 60, 0.1, 0.7, 12, "dairy gluten", {"Semolina (rava)": 60, "Curd": 40, "Cooking oil / ghee": 6}),
    ("rava_upma", "Rava upma", "1 cup", 250, 6, 36, 9, 2, 1.2, 20, 0, 0.6, 10, "gluten onion_garlic", {"Semolina (rava)": 50, "Onions": 30, "Cooking oil / ghee": 8}),
    ("poha", "Kanda poha", "1 cup", 250, 5, 42, 7, 2, 2.5, 15, 0, 0.6, 8, "onion_garlic peanut", {"Poha": 60, "Onions": 30, "Peanuts": 10, "Cooking oil / ghee": 6}),
    ("poha_plain", "Poha without onion (dadpe / chire)", "1 cup", 230, 5, 40, 6, 2, 2.5, 15, 0, 0.6, 7, "peanut", {"Poha": 60, "Peanuts": 10, "Cooking oil / ghee": 5}),
    ("besan_cheela", "Besan cheela", "2 pieces", 250, 12, 28, 9, 5, 2.8, 45, 0, 1.6, 10, "onion_garlic", {"Besan": 60, "Onions": 20, "Cooking oil / ghee": 8}),
    ("moong_chilla", "Moong dal chilla", "2 pieces", 230, 13, 30, 6, 6, 2.6, 45, 0, 1.4, 12, "", {"Moong dal": 60, "Cooking oil / ghee": 6}),
    ("oats_porridge", "Oats cooked in milk", "1 bowl", 300, 13, 42, 9, 4, 2.0, 260, 0.9, 2.0, 20, "dairy", {"Rolled oats": 40, "Milk (ml)": 200}),
    ("oats_plain", "Oats (cooked in water)", "40 g dry", 150, 5.3, 27, 2.6, 4, 1.7, 20, 0, 1.6, 8, "", {"Rolled oats": 40}),
    ("oats_savory", "Vegetable masala oats", "1 bowl", 220, 8, 34, 6, 5, 2.0, 30, 0, 1.6, 15, "onion_garlic", {"Rolled oats": 45, "Mixed vegetables": 60, "Cooking oil / ghee": 5}),
    ("ven_pongal", "Ven pongal", "1 cup", 300, 9, 45, 9, 3, 1.4, 30, 0, 1.0, 12, "dairy", {"Rice": 45, "Moong dal": 20, "Cooking oil / ghee": 8}),
    ("dhokla", "Khaman dhokla", "4 pieces", 160, 7, 22, 5, 2.5, 1.5, 30, 0, 0.8, 10, "", {"Besan": 45, "Cooking oil / ghee": 4}),
    ("handvo", "Handvo", "1 slice", 220, 8, 30, 8, 4, 2.0, 50, 0, 1.0, 12, "dairy", {"Rice": 25, "Toor dal": 15, "Curd": 30, "Bottle gourd (lauki)": 40, "Cooking oil / ghee": 6}),
    ("khakhra", "Methi khakhra", "2 pieces", 120, 3.5, 18, 4, 3, 1.2, 15, 0, 0.6, 8, "gluten", {"Khakhra (pcs)": 2}),
    ("misal", "Misal pav", "1 plate", 450, 17, 58, 16, 10, 4.5, 80, 0, 2.0, 30, "gluten onion_garlic", {"Moth beans (matki)": 60, "Pav (pcs)": 2, "Onions": 40, "Cooking oil / ghee": 12}),
    ("thalipeeth", "Thalipeeth", "2 pieces", 280, 10, 40, 8, 7, 3.0, 60, 0, 1.6, 10, "onion_garlic", {"Bhajani (multigrain) flour": 70, "Onions": 30, "Cooking oil / ghee": 6}),
    ("idiyappam", "Idiyappam", "2 pieces", 180, 3, 40, 0.5, 1, 0.5, 10, 0, 0.5, 10, "", {"Rice flour": 50}),
    ("appam", "Appam", "2 pieces", 220, 4, 42, 4, 1.5, 0.6, 10, 0, 0.6, 12, "coconut", {"Idli rice": 55, "Coconut": 15}),
    ("sabudana_khichdi", "Sabudana khichdi", "1 cup", 330, 5, 55, 11, 1.5, 1.2, 20, 0, 0.4, 18, "peanut fasting root dairy", {"Sabudana": 70, "Peanuts": 20, "Potatoes": 40, "Cooking oil / ghee": 6}),
    ("kuttu_cheela", "Kuttu (buckwheat) cheela", "2 pieces", 220, 7, 34, 6, 5, 2.0, 20, 0, 1.6, 15, "fasting dairy", {"Kuttu atta": 55, "Cooking oil / ghee": 5}),
    ("rajgira_paratha", "Rajgira paratha", "2 pieces", 220, 7, 34, 6, 4, 4.0, 80, 0, 1.5, 15, "fasting root dairy", {"Rajgira atta": 45, "Potatoes": 40, "Cooking oil / ghee": 6}),

    # ── Dals and legumes ────────────────────────────────────────────────
    ("dal_tadka", "Dal tadka", "1 cup", 190, 10, 26, 5, 5, 2.0, 40, 0, 1.2, 12, "onion_garlic", {"Toor dal": 50, "Onions": 20, "Tomatoes": 30, "Cooking oil / ghee": 5}),
    ("dal_jain", "Plain toor dal (hing-jeera)", "1 cup", 170, 10, 26, 3, 5, 2.0, 35, 0, 1.2, 10, "", {"Toor dal": 50, "Tomatoes": 30, "Cooking oil / ghee": 4}),
    ("moong_dal", "Yellow moong dal", "1 cup", 180, 12, 26, 3, 6, 2.2, 40, 0, 1.3, 12, "", {"Moong dal": 50, "Cooking oil / ghee": 4}),
    ("masoor_dal", "Masoor dal", "1 cup", 190, 13, 26, 3.5, 7, 3.5, 30, 0, 1.6, 10, "onion_garlic", {"Masoor dal": 50, "Onions": 20, "Cooking oil / ghee": 4}),
    ("dal_makhani", "Dal makhani", "1 cup", 300, 13, 30, 14, 9, 4.0, 90, 0.1, 2.0, 25, "dairy onion_garlic", {"Whole urad dal": 50, "Rajma": 10, "Butter / cream": 15, "Onions": 20}),
    ("rajma", "Rajma curry", "1 cup", 240, 13, 34, 6, 10, 4.0, 70, 0, 1.6, 15, "onion_garlic", {"Rajma": 60, "Onions": 40, "Tomatoes": 50, "Cooking oil / ghee": 6}),
    ("chole", "Chole (chana masala)", "1 cup", 270, 13, 38, 8, 10, 4.2, 70, 0, 2.0, 15, "onion_garlic", {"Kabuli chana": 65, "Onions": 40, "Tomatoes": 50, "Cooking oil / ghee": 8}),
    ("chole_jain", "Chole without onion-garlic", "1 cup", 250, 13, 38, 6, 10, 4.2, 65, 0, 2.0, 14, "", {"Kabuli chana": 65, "Tomatoes": 60, "Cooking oil / ghee": 6}),
    ("kala_chana", "Kala chana curry", "1 cup", 240, 12, 36, 6, 11, 4.5, 80, 0, 2.2, 10, "onion_garlic", {"Kala chana": 60, "Onions": 30, "Tomatoes": 40, "Cooking oil / ghee": 6}),
    ("sambar", "Sambar", "1 cup", 150, 7, 22, 4, 5, 1.8, 50, 0, 0.9, 12, "onion_garlic", {"Toor dal": 30, "Mixed vegetables": 80, "Tamarind": 5, "Cooking oil / ghee": 4}),
    ("rasam", "Rasam", "1 cup", 70, 2.5, 10, 2, 1.5, 0.8, 20, 0, 0.3, 5, "onion_garlic", {"Toor dal": 10, "Tomatoes": 60}),
    ("kadhi", "Gujarati kadhi", "1 cup", 170, 7, 15, 9, 1.5, 1.0, 160, 0.4, 0.8, 10, "dairy", {"Curd": 150, "Besan": 20, "Cooking oil / ghee": 4}),
    ("dal_dhokli", "Dal dhokli", "1 bowl", 380, 14, 58, 10, 9, 3.5, 60, 0, 1.8, 15, "gluten dairy", {"Toor dal": 45, "Whole wheat atta": 50, "Cooking oil / ghee": 6, "Jaggery": 8}),
    ("cholar_dal", "Cholar dal", "1 cup", 260, 12, 32, 9, 8, 2.8, 40, 0, 2.0, 14, "coconut dairy", {"Chana dal": 55, "Coconut": 10, "Cooking oil / ghee": 6}),
    ("sprouts_usal", "Sprouts usal", "1 cup", 200, 12, 26, 6, 8, 3.0, 50, 0, 1.5, 10, "onion_garlic", {"Sprouted moong": 120, "Onions": 20, "Cooking oil / ghee": 5}),
    ("dal_khichdi", "Moong dal khichdi", "1 bowl", 330, 12, 55, 7, 5, 2.4, 40, 0, 1.5, 12, "dairy", {"Rice": 50, "Moong dal": 30, "Mixed vegetables": 50, "Cooking oil / ghee": 6}),
    ("bisi_bele_bath", "Bisi bele bath", "1 bowl", 400, 13, 62, 11, 8, 3.0, 60, 0, 1.8, 18, "dairy", {"Rice": 50, "Toor dal": 30, "Mixed vegetables": 80, "Cooking oil / ghee": 8}),
    ("sundal", "Chickpea sundal", "1 cup", 210, 11, 30, 5, 9, 3.5, 60, 0, 1.8, 8, "coconut", {"Kabuli chana": 50, "Coconut": 10}),

    # ── Paneer, tofu, soy, eggs ─────────────────────────────────────────
    ("paneer_bhurji", "Paneer bhurji", "1 cup", 330, 20, 8, 24, 2, 0.8, 420, 0.6, 2.5, 50, "dairy onion_garlic", {"Paneer": 120, "Onions": 30, "Tomatoes": 40, "Cooking oil / ghee": 6}),
    ("palak_paneer", "Palak paneer", "1 cup", 300, 16, 12, 21, 4, 3.5, 420, 0.4, 2.2, 45, "dairy onion_garlic", {"Paneer": 80, "Spinach (palak)": 150, "Onions": 30, "Cooking oil / ghee": 6}),
    ("paneer_butter_masala", "Paneer butter masala", "1 cup", 380, 15, 14, 29, 2.5, 1.5, 380, 0.4, 2.0, 55, "dairy onion_garlic nuts", {"Paneer": 80, "Tomatoes": 100, "Butter / cream": 20, "Cashews": 8}),
    ("matar_paneer", "Matar paneer", "1 cup", 300, 16, 16, 19, 5, 2.0, 350, 0.4, 2.2, 45, "dairy onion_garlic", {"Paneer": 70, "Green peas": 60, "Tomatoes": 60, "Cooking oil / ghee": 6}),
    ("paneer_jain", "Paneer capsicum tomato (Jain)", "1 cup", 290, 16, 9, 21, 2, 1.2, 380, 0.4, 2.0, 45, "dairy", {"Paneer": 80, "Tomatoes": 80, "Capsicum": 50, "Cooking oil / ghee": 6}),
    ("paneer_tikka", "Paneer tikka", "6 pieces", 320, 22, 9, 22, 2, 1.0, 450, 0.6, 2.8, 60, "dairy onion_garlic", {"Paneer": 130, "Curd": 30, "Capsicum": 40, "Onions": 30}),
    ("paneer_cubes", "Paneer cubes", "100 g", 265, 18, 3, 20, 0, 0.2, 480, 0.4, 2.7, 40, "dairy fasting", {"Paneer": 100}),
    ("tofu_stirfry", "Tofu vegetable stir-fry", "1 bowl", 260, 20, 12, 15, 4, 4.0, 450, 0, 2.0, 45, "soy onion_garlic", {"Tofu": 150, "Mixed vegetables": 100, "Cooking oil / ghee": 6}),
    ("tofu_bhurji", "Tofu bhurji", "1 cup", 230, 18, 8, 14, 3, 3.5, 400, 0, 1.8, 40, "soy onion_garlic", {"Tofu": 150, "Onions": 30, "Tomatoes": 40, "Cooking oil / ghee": 6}),
    ("soya_curry", "Soya chunks curry", "1 cup", 220, 21, 18, 6, 6, 8.0, 100, 0, 2.0, 12, "soy onion_garlic", {"Soya chunks": 40, "Onions": 30, "Tomatoes": 50, "Cooking oil / ghee": 6}),
    ("soya_jain", "Soya chunks in tomato gravy (no onion-garlic)", "1 cup", 210, 21, 17, 6, 6, 8.0, 100, 0, 2.0, 12, "soy", {"Soya chunks": 40, "Tomatoes": 70, "Cooking oil / ghee": 6}),
    ("boiled_eggs", "Boiled eggs", "2 eggs", 155, 12.5, 1, 10.5, 0, 1.7, 55, 1.1, 1.3, 14, "egg", {"Eggs (pcs)": 2}),
    ("egg_bhurji", "Egg bhurji", "2 eggs", 220, 13, 4, 17, 1, 2.0, 60, 1.1, 1.3, 18, "egg onion_garlic", {"Eggs (pcs)": 2, "Onions": 30, "Cooking oil / ghee": 5}),
    ("egg_curry", "Egg curry", "2 eggs", 280, 14, 10, 20, 2, 2.4, 70, 1.1, 1.5, 25, "egg onion_garlic", {"Eggs (pcs)": 2, "Onions": 40, "Tomatoes": 50, "Cooking oil / ghee": 8}),

    # ── Vegetables ─────────────────────────────────────────────────────
    ("mixed_veg", "Mixed vegetable sabzi", "1 cup", 120, 3.5, 14, 6, 5, 1.5, 50, 0, 0.6, 15, "onion_garlic", {"Mixed vegetables": 150, "Onions": 20, "Cooking oil / ghee": 6}),
    ("aloo_gobi", "Aloo gobi", "1 cup", 170, 4, 22, 8, 5, 1.2, 35, 0, 0.6, 12, "root onion_garlic", {"Potatoes": 80, "Cauliflower": 100, "Cooking oil / ghee": 8}),
    ("bhindi", "Bhindi sabzi", "1 cup", 140, 3, 12, 9, 5, 0.9, 120, 0, 0.8, 15, "onion_garlic", {"Okra (bhindi)": 150, "Onions": 20, "Cooking oil / ghee": 8}),
    ("cabbage_poriyal", "Cabbage poriyal / palya", "1 cup", 110, 3, 11, 6, 4, 0.8, 60, 0, 0.4, 8, "coconut", {"Cabbage": 150, "Coconut": 10, "Cooking oil / ghee": 5}),
    ("beans_poriyal", "Beans poriyal", "1 cup", 110, 3, 11, 6, 5, 1.3, 50, 0, 0.4, 12, "coconut", {"French beans": 150, "Coconut": 10, "Cooking oil / ghee": 5}),
    ("baingan_bharta", "Baingan bharta", "1 cup", 140, 3, 14, 8, 6, 0.8, 30, 0, 0.4, 12, "onion_garlic", {"Brinjal": 200, "Onions": 30, "Cooking oil / ghee": 8}),
    ("lauki_sabzi", "Lauki sabzi", "1 cup", 90, 2, 10, 5, 3, 0.6, 40, 0, 0.4, 8, "fasting", {"Bottle gourd (lauki)": 200, "Tomatoes": 30, "Cooking oil / ghee": 5}),
    ("undhiyu", "Undhiyu", "1 cup", 280, 7, 30, 15, 8, 2.0, 70, 0, 1.0, 25, "root", {"Mixed vegetables": 120, "Sweet potato": 50, "Surti papdi": 50, "Cooking oil / ghee": 12}),
    ("avial", "Avial", "1 cup", 200, 4, 14, 14, 5, 1.2, 80, 0.2, 0.6, 20, "coconut dairy root", {"Mixed vegetables": 150, "Coconut": 30, "Curd": 30}),
    ("veg_stew", "Kerala vegetable stew", "1 cup", 190, 3, 16, 13, 4, 1.0, 40, 0, 0.5, 18, "coconut root", {"Mixed vegetables": 120, "Potatoes": 50, "Coconut milk (ml)": 80}),
    ("kootu", "Kootu", "1 cup", 160, 7, 18, 7, 5, 1.6, 60, 0, 0.9, 12, "coconut", {"Moong dal": 25, "Mixed vegetables": 100, "Coconut": 15}),
    ("aloo_vrat", "Jeera aloo (vrat style)", "1 cup", 180, 3, 28, 7, 3, 1.0, 15, 0, 0.5, 8, "root fasting dairy", {"Potatoes": 150, "Cooking oil / ghee": 6}),
    ("salad", "Cucumber-tomato salad", "1 bowl", 35, 1.5, 7, 0.3, 2, 0.5, 25, 0, 0.3, 10, "fasting", {"Cucumber": 100, "Tomatoes": 60}),

    # ── Dairy and drinks ──────────────────────────────────────────────
    ("curd", "Curd (dahi)", "1 cup, 200 g", 120, 7, 9, 6, 0, 0.2, 240, 0.6, 1.0, 15, "dairy fasting", {"Curd": 200}),
    ("raita", "Cucumber raita", "1 cup", 110, 6, 9, 5, 0.6, 0.3, 200, 0.5, 0.9, 14, "dairy fasting", {"Curd": 170, "Cucumber": 40}),
    ("greek_yogurt", "Greek yogurt / hung curd", "150 g", 100, 15, 6, 1, 0, 0.1, 165, 1.1, 0.8, 50, "dairy fasting", {"Greek yogurt": 150}),
    ("milk", "Milk", "1 glass, 250 ml", 150, 8, 12, 8, 0, 0.1, 300, 1.1, 1.0, 15, "dairy fasting", {"Milk (ml)": 250}),
    ("buttermilk", "Chaas (buttermilk)", "1 glass", 40, 3, 4, 1, 0, 0.1, 120, 0.3, 0.4, 5, "dairy fasting", {"Curd": 80}),
    ("masala_chai", "Masala chai", "1 cup", 90, 3, 12, 3, 0, 0.2, 100, 0.3, 0.3, 6, "dairy fasting", {"Milk (ml)": 100, "Sugar": 8, "Tea leaves": 3}),
    ("soy_milk", "Fortified soy milk", "1 glass, 250 ml", 100, 7, 6, 4, 1, 1.0, 300, 1.0, 0.6, 25, "soy", {"Soy milk (ml)": 250}),
    ("smoothie_pb", "Banana peanut butter smoothie", "1 glass", 350, 15, 45, 13, 4, 1.0, 300, 1.1, 1.6, 35, "dairy peanut", {"Milk (ml)": 250, "Bananas (pcs)": 1, "Peanut butter": 16}),
    ("ragi_malt", "Ragi malt", "1 glass", 180, 6, 30, 4, 3, 1.3, 250, 0.6, 1.1, 10, "dairy", {"Ragi flour": 30, "Milk (ml)": 150, "Jaggery": 10}),
    ("sattu_drink", "Sattu sharbat", "1 glass", 160, 9, 26, 2, 7, 3.0, 20, 0, 1.4, 6, "", {"Sattu": 40}),

    # ── Chutneys and sides ─────────────────────────────────────────────
    ("coconut_chutney", "Coconut chutney", "2 tbsp", 70, 1, 3, 6, 1.5, 0.3, 5, 0, 0.2, 4, "coconut", {"Coconut": 25, "Roasted chana": 5}),
    ("peanut_chutney", "Peanut chutney", "3 tbsp", 120, 5, 4, 9, 2, 0.5, 15, 0, 0.6, 4, "peanut fasting", {"Peanuts": 25}),
    ("green_chutney", "Green chutney", "2 tbsp", 15, 0.5, 2, 0.5, 1, 0.6, 20, 0, 0.1, 2, "", {"Coriander and mint": 30}),
    ("papad", "Roasted papad", "1 piece", 35, 2.5, 6, 0.3, 1.5, 0.7, 8, 0, 0.3, 2, "", {"Papad (pcs)": 1}),

    # ── Snacks, fruit, nuts, seeds ─────────────────────────────────────
    ("roasted_chana", "Roasted chana", "50 g", 180, 10, 29, 2.5, 8, 4.7, 29, 0, 2.5, 6, "", {"Roasted chana": 50}),
    ("peanuts", "Roasted peanuts", "30 g", 170, 7.7, 5, 14, 2.5, 0.8, 18, 0, 1.0, 5, "peanut fasting", {"Peanuts": 30}),
    ("makhana", "Roasted makhana", "30 g", 110, 3, 22, 1, 2, 0.4, 18, 0, 0.3, 18, "fasting dairy", {"Makhana": 30, "Cooking oil / ghee": 3}),
    ("sprouts_chaat", "Sprouts chaat", "1 cup", 140, 10, 22, 1.5, 6, 2.3, 30, 0, 1.2, 10, "onion_garlic", {"Sprouted moong": 130, "Onions": 20, "Tomatoes": 30}),
    ("fruit", "Seasonal fruit", "1 bowl", 90, 1, 22, 0.3, 3, 0.4, 20, 0, 0.2, 20, "fasting", {"Seasonal fruit": 150}),
    ("banana", "Banana", "1 medium", 105, 1.3, 27, 0.4, 3, 0.3, 6, 0, 0.2, 6, "fasting", {"Bananas (pcs)": 1}),
    ("apple", "Apple", "1 medium", 95, 0.5, 25, 0.3, 4.4, 0.2, 11, 0, 0.1, 25, "fasting", {"Apples (pcs)": 1}),
    ("peanut_butter", "Peanut butter", "2 tbsp", 190, 8, 6, 16, 2, 0.6, 15, 0, 0.9, 15, "peanut", {"Peanut butter": 32}),
    ("almonds", "Almonds", "20 g", 115, 4.2, 4.3, 10, 2.5, 0.8, 54, 0, 0.6, 22, "nuts fasting", {"Almonds": 20}),
    ("chia", "Chia seeds", "2 tbsp", 98, 3.3, 8.4, 6.2, 6.9, 1.5, 126, 0, 0.9, 15, "", {"Chia seeds": 20}),
    ("flax", "Ground flaxseed", "1 tbsp", 53, 1.8, 2.9, 4.2, 2.7, 0.6, 26, 0, 0.4, 3, "", {"Flaxseed": 10}),
    ("pumpkin_seeds", "Pumpkin seeds", "15 g", 85, 4.5, 2, 7, 1, 1.2, 7, 0, 1.2, 15, "", {"Pumpkin seeds": 15}),
    ("chikki", "Peanut chikki", "1 piece, 30 g", 150, 4.5, 15, 8, 1.5, 0.9, 15, 0, 0.6, 10, "peanut fasting", {"Peanut chikki": 30}),
]

FIELDS = ("kcal", "protein", "carbs", "fat", "fiber", "iron", "calcium", "b12", "zinc", "cost")

COMPONENTS = {}
for row in _RAW:
    key, name, serving = row[0], row[1], row[2]
    values = dict(zip(FIELDS, row[3:13]))
    COMPONENTS[key] = {
        "key": key, "name": name, "serving": serving, **values,
        "tags": set(row[13].split()), "grocery": row[14],
    }

# Foods offered in the quick log search. Every component is loggable.
LOGGABLE = sorted(COMPONENTS.values(), key=lambda c: c["name"])

# Grocery aisle for each raw ingredient (used to group the shopping list)
AISLES = {
    "Pulses and legumes": ["Toor dal", "Moong dal", "Masoor dal", "Chana dal", "Urad dal", "Whole urad dal", "Whole green moong",
                           "Rajma", "Kabuli chana", "Kala chana", "Moth beans (matki)", "Sprouted moong", "Soya chunks", "Roasted chana", "Sattu", "Besan"],
    "Dairy, tofu and eggs": ["Paneer", "Curd", "Greek yogurt", "Milk (ml)", "Butter / cream", "Tofu", "Soy milk (ml)", "Eggs (pcs)"],
    "Grains and flours": ["Whole wheat atta", "Rice", "Brown rice", "Idli rice", "Rice flour", "Quinoa", "Rolled oats", "Poha", "Semolina (rava)",
                          "Jowar flour", "Bajra flour", "Ragi flour", "Bhajani (multigrain) flour", "Samak rice", "Sabudana", "Kuttu atta", "Rajgira atta",
                          "Pav (pcs)", "Khakhra (pcs)", "Papad (pcs)"],
    "Vegetables": ["Onions", "Tomatoes", "Potatoes", "Sweet potato", "Mixed vegetables", "Spinach (palak)", "Methi leaves", "Cauliflower", "Okra (bhindi)",
                   "Cabbage", "French beans", "Brinjal", "Bottle gourd (lauki)", "Surti papdi", "Green peas", "Capsicum", "Cucumber", "Coriander and mint"],
    "Fruit": ["Bananas (pcs)", "Apples (pcs)", "Seasonal fruit"],
    "Nuts and seeds": ["Peanuts", "Peanut butter", "Almonds", "Cashews", "Chia seeds", "Flaxseed", "Pumpkin seeds", "Makhana", "Peanut chikki", "Coconut", "Coconut milk (ml)"],
    "Pantry": ["Cooking oil / ghee", "Jaggery", "Sugar", "Tea leaves", "Tamarind"],
}
AISLE_OF = {item: aisle for aisle, items in AISLES.items() for item in items}


def search_components(query, limit=15):
    q = (query or "").strip().lower()
    if not q:
        return []
    starts = [c for c in LOGGABLE if c["name"].lower().startswith(q)]
    contains = [c for c in LOGGABLE if q in c["name"].lower() and c not in starts]
    return (starts + contains)[:limit]
