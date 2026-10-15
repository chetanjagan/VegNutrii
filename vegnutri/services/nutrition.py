"""Energy targets, diet-mode rules and micronutrient reference values."""

GOALS = {"fat_loss": "Lose fat", "maintenance": "Maintain weight", "muscle_gain": "Build muscle"}
ACTIVITY = {
    "sedentary": ("Mostly sitting", 1.2),
    "light": ("Light exercise 1-3 days/week", 1.375),
    "moderate": ("Exercise 3-5 days/week", 1.55),
    "active": ("Hard exercise 6-7 days/week", 1.725),
    "very_active": ("Physical job or twice-daily training", 1.9),
}

# Diet modes and the tags each one excludes.
DIET_MODES = {
    "vegetarian": ("Vegetarian (lacto)", {"egg"}),
    "eggetarian": ("Eggetarian", set()),
    "vegan": ("Vegan", {"dairy", "egg", "honey"}),
    "jain": ("Jain", {"egg", "onion_garlic", "root", "honey", "mushroom"}),
    "sattvic": ("Sattvic / no onion-garlic", {"egg", "onion_garlic", "mushroom"}),
    "lactose_free": ("Lactose-free vegetarian", {"egg", "dairy"}),
}

# Allergy / intolerance options mapped to tags.
ALLERGIES = {
    "peanut": "Peanuts",
    "nuts": "Tree nuts",
    "gluten": "Gluten (wheat)",
    "soy": "Soy",
    "dairy": "Dairy",
    "sesame": "Sesame",
    "coconut": "Coconut",
}

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Reference intakes for Indian adults, per day, from ICMR-NIN "Nutrient
# Requirements for Indians" (2020). Used for gentle guidance, not diagnosis.
RDA = {
    "male": {"iron": 19.0, "calcium": 1000.0, "b12": 2.5, "zinc": 17.0},
    "female": {"iron": 29.0, "calcium": 1000.0, "b12": 2.5, "zinc": 13.2},
}
MICRO_LABELS = {
    "iron": ("Iron", "mg", "Pair dals, palak and rajma with lemon or tomato. Vitamin C helps absorption. Avoid tea right after meals."),
    "calcium": ("Calcium", "mg", "Curd, paneer, ragi, tofu (calcium-set) and sesame are your strongest sources."),
    "b12": ("Vitamin B12", "mcg", "Milk, curd and paneer give some B12. Many vegetarians still need a supplement; ask your doctor to test your levels."),
    "zinc": ("Zinc", "mg", "Pumpkin seeds, chickpeas, cashews and sprouted or fermented foods (idli, dosa) help."),
}

MIN_CALORIES = {"male": 1500, "female": 1200}


def calculate_targets(age, height_cm, weight_kg, gender, goal, activity):
    """Mifflin-St Jeor BMR x activity factor, adjusted for goal.

    Returns (calories, protein_g). Calories never drop below a safe floor and
    the deficit is capped at 20% of maintenance.
    """
    gender = "female" if gender == "female" else "male"
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + (5 if gender == "male" else -161)
    tdee = bmr * ACTIVITY.get(activity, ACTIVITY["sedentary"])[1]
    if goal == "fat_loss":
        calories = max(tdee - 500, tdee * 0.8)
        protein_per_kg = 1.4
    elif goal == "muscle_gain":
        calories = tdee + 300
        protein_per_kg = 1.6
    else:
        calories = tdee
        protein_per_kg = 1.1
    calories = max(calories, MIN_CALORIES[gender])
    # Protein: per kg body weight, capped at 30% of energy so targets stay
    # reachable on a vegetarian diet and for heavier users.
    protein = min(weight_kg * protein_per_kg, calories * 0.30 / 4)
    return int(round(calories / 10) * 10), int(round(protein))


def water_goal_ml(weight_kg, activity):
    base = weight_kg * 35
    if activity in ("active", "very_active"):
        base += 500
    return int(min(max(round(base / 250) * 250, 2000), 4000))


def excluded_tags(diet_mode, allergies):
    tags = set(DIET_MODES.get(diet_mode, DIET_MODES["vegetarian"])[1])
    tags |= set(allergies or [])
    return tags


def bmi_stats(height_cm, weight_kg):
    h = height_cm / 100
    bmi = round(weight_kg / (h * h), 1)
    # WHO Asian cut-offs (Indians carry higher risk at lower BMI)
    if bmi < 18.5:
        cat = "Underweight"
    elif bmi < 23:
        cat = "Healthy range"
    elif bmi < 25:
        cat = "Overweight (Asian cut-off)"
    else:
        cat = "Obese (Asian cut-off)"
    low, high = round(18.5 * h * h, 1), round(22.9 * h * h, 1)
    return {"bmi": bmi, "category": cat, "healthy_low": low, "healthy_high": high}


# Approximate daily energy (kcal) and protein (g) for children, based on
# ICMR-NIN 2020 reference values for moderately active Indian children.
CHILD_BANDS = [  # (max_age, kcal_boy, kcal_girl, protein)
    (3, 1070, 1070, 12.5),
    (6, 1360, 1360, 16),
    (9, 1700, 1700, 23),
    (12, 2220, 2060, 32),
]


def member_targets(age, height_cm, weight_kg, gender, goal, activity):
    """Targets for a household member. Children get reference values, never a deficit."""
    if age < 13:
        for max_age, boy, girl, protein in CHILD_BANDS:
            if age <= max_age:
                return (girl if gender == "female" else boy), int(protein)
    if age < 18:
        goal = "maintenance"
    return calculate_targets(age, height_cm, weight_kg, gender, goal, activity)
