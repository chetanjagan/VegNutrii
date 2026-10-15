from vegnutri.services.nutrition import bmi_stats, calculate_targets, excluded_tags, member_targets, water_goal_ml


def test_fat_loss_never_below_safe_floor():
    # Small, sedentary woman: raw maths would go below 1200 kcal
    kcal, protein = calculate_targets(55, 148, 42, "female", "fat_loss", "sedentary")
    assert kcal >= 1200
    assert protein * 4 <= kcal * 0.30 + 4


def test_fat_loss_deficit_capped_at_20_percent():
    maint, _ = calculate_targets(30, 175, 80, "male", "maintenance", "moderate")
    loss, _ = calculate_targets(30, 175, 80, "male", "fat_loss", "moderate")
    assert loss >= maint * 0.8 - 10


def test_muscle_gain_above_maintenance():
    maint, p1 = calculate_targets(25, 175, 70, "male", "maintenance", "active")
    gain, p2 = calculate_targets(25, 175, 70, "male", "muscle_gain", "active")
    assert gain > maint and p2 > p1


def test_children_get_reference_values_not_deficits():
    kcal, protein = member_targets(8, 125, 25, "female", "fat_loss", "light")
    assert kcal == 1700 and protein == 23
    teen_loss, _ = member_targets(15, 160, 70, "male", "fat_loss", "light")
    teen_maint, _ = calculate_targets(15, 160, 70, "male", "maintenance", "light")
    assert teen_loss == teen_maint


def test_diet_mode_exclusions():
    assert {"onion_garlic", "root", "egg", "honey"} <= excluded_tags("jain", [])
    assert {"dairy", "egg"} <= excluded_tags("vegan", [])
    assert "egg" not in excluded_tags("eggetarian", [])
    assert "peanut" in excluded_tags("vegetarian", ["peanut"])


def test_water_goal_bounds():
    assert water_goal_ml(40, "sedentary") == 2000
    assert water_goal_ml(150, "very_active") == 4000


def test_bmi_uses_asian_cutoffs():
    assert bmi_stats(165, 65)["category"].startswith("Overweight")  # BMI 23.9
