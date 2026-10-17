from datetime import date, datetime, timezone

from flask_login import UserMixin
from sqlalchemy import false, true
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    accepted_terms_at = db.Column(db.DateTime)
    marketing_opt_in = db.Column(db.Boolean, default=False, nullable=False)

    plan = db.Column(db.String(20), default="free", nullable=False)  # free | pro | family
    plan_expires_at = db.Column(db.DateTime)
    on_trial = db.Column(db.Boolean, default=False, server_default=false(), nullable=False)

    # Referrals: code is created on first use; referred_by_id is who invited this user
    referral_code = db.Column(db.String(12), unique=True, index=True)
    referred_by_id = db.Column(db.Integer)
    referral_rewards = db.Column(db.Integer, default=0, server_default="0", nullable=False)

    # Weekly progress email
    weekly_digest = db.Column(db.Boolean, default=True, server_default=true(), nullable=False)
    last_digest_at = db.Column(db.DateTime)

    profile = db.relationship("Profile", uselist=False, back_populates="user", cascade="all, delete-orphan")

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        if not self.password_hash:
            return False
        if ":" in self.password_hash:  # werkzeug format
            return check_password_hash(self.password_hash, raw)
        # Legacy unsalted SHA-256 hashes imported from VegNutri v3. Upgraded on login.
        import hashlib
        import secrets
        return secrets.compare_digest(self.password_hash, hashlib.sha256(raw.encode()).hexdigest())

    @property
    def has_legacy_hash(self):
        return bool(self.password_hash) and ":" not in self.password_hash

    @property
    def admin_preview(self):
        """For admins: the plan they're previewing the app as (set from /admin), else None."""
        if not self.is_admin:
            return None
        from flask import has_request_context, session
        if has_request_context():
            plan = session.get("admin_preview")
            if plan in ("free", "pro", "family"):
                return plan
        return None

    @property
    def active_plan(self):
        """The plan the user can use right now (expired paid plans fall back to free).

        Admins get Family (everything) so they can use and check every feature,
        unless they've chosen to preview the app as another plan.
        """
        if self.is_admin:
            return self.admin_preview or "family"
        if self.plan in ("pro", "family") and self.plan_expires_at and self.plan_expires_at > utcnow():
            return self.plan
        return "free"

    @property
    def is_paid(self):
        return self.active_plan != "free"

    @property
    def trial_days_left(self):
        """Whole days left on a running trial, else None."""
        if self.is_admin or not self.on_trial or self.active_plan == "free":
            return None
        return max((self.plan_expires_at - utcnow()).days + 1, 0)

    def ensure_referral_code(self):
        if not self.referral_code:
            import secrets
            alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I confusion
            while True:
                code = "".join(secrets.choice(alphabet) for _ in range(8))
                if not User.query.filter_by(referral_code=code).first():
                    self.referral_code = code
                    break
        return self.referral_code


class Profile(db.Model):
    __tablename__ = "profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    age = db.Column(db.Integer, nullable=False)
    height = db.Column(db.Float, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    goal = db.Column(db.String(20), nullable=False)
    activity_level = db.Column(db.String(20), nullable=False)
    cuisine = db.Column(db.String(30), default="north_indian", nullable=False)
    diet_mode = db.Column(db.String(30), default="vegetarian", nullable=False)
    allergies = db.Column(db.String(200), default="", nullable=False)  # comma-separated tags
    cooking_time = db.Column(db.Integer, default=30, nullable=False)
    daily_budget = db.Column(db.Integer, default=0, nullable=False)  # INR per day, 0 = no limit
    fasting_days = db.Column(db.String(20), default="", nullable=False)  # weekday numbers, "0,3"
    daily_calories = db.Column(db.Integer, nullable=False)
    daily_protein = db.Column(db.Integer, nullable=False)
    water_goal_ml = db.Column(db.Integer, default=2500, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    user = db.relationship("User", back_populates="profile")

    @property
    def allergy_list(self):
        return [a for a in (self.allergies or "").split(",") if a]

    @property
    def fasting_weekdays(self):
        return [int(d) for d in (self.fasting_days or "").split(",") if d.strip().isdigit()]


class MealLog(db.Model):
    __tablename__ = "meal_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    meal_type = db.Column(db.String(20), nullable=False)
    servings = db.Column(db.Float, default=1.0, nullable=False)
    calories = db.Column(db.Float, default=0, nullable=False)
    protein = db.Column(db.Float, default=0, nullable=False)
    carbs = db.Column(db.Float, default=0, nullable=False)
    fat = db.Column(db.Float, default=0, nullable=False)
    fiber = db.Column(db.Float, default=0, nullable=False)
    iron = db.Column(db.Float, default=0, nullable=False)
    calcium = db.Column(db.Float, default=0, nullable=False)
    b12 = db.Column(db.Float, default=0, nullable=False)
    zinc = db.Column(db.Float, default=0, nullable=False)
    log_date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class WeightLog(db.Model):
    __tablename__ = "weight_logs"
    __table_args__ = (db.UniqueConstraint("user_id", "log_date"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    weight = db.Column(db.Float, nullable=False)
    log_date = db.Column(db.Date, default=date.today, nullable=False)


class WaterLog(db.Model):
    __tablename__ = "water_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount_ml = db.Column(db.Integer, nullable=False)
    log_date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class MoodLog(db.Model):
    __tablename__ = "mood_logs"
    __table_args__ = (db.UniqueConstraint("user_id", "log_date"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mood = db.Column(db.String(20), nullable=False)
    energy_level = db.Column(db.Integer, default=3, nullable=False)
    note = db.Column(db.String(500), default="", nullable=False)
    log_date = db.Column(db.Date, default=date.today, nullable=False)


class CustomFood(db.Model):
    __tablename__ = "custom_foods"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    serving_size = db.Column(db.String(60), default="1 serving", nullable=False)
    calories = db.Column(db.Float, default=0, nullable=False)
    protein = db.Column(db.Float, default=0, nullable=False)
    carbs = db.Column(db.Float, default=0, nullable=False)
    fat = db.Column(db.Float, default=0, nullable=False)
    fiber = db.Column(db.Float, default=0, nullable=False)
    iron = db.Column(db.Float, default=0, nullable=False)
    calcium = db.Column(db.Float, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class MealPlan(db.Model):
    __tablename__ = "meal_plans"
    __table_args__ = (db.UniqueConstraint("user_id", "plan_date"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_date = db.Column(db.Date, nullable=False)
    data = db.Column(db.JSON, nullable=False)  # {"breakfast": {...}, ..., "scale": 1.0, "fasting": bool}
    total_calories = db.Column(db.Float, default=0, nullable=False)
    total_protein = db.Column(db.Float, default=0, nullable=False)
    total_cost = db.Column(db.Float, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = db.Column(db.String(10), nullable=False)  # user | assistant
    content = db.Column(db.Text, nullable=False)
    cleared = db.Column(db.Boolean, default=False, nullable=False)  # hidden by "clear chat", still counts to quota
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)


class HouseholdMember(db.Model):
    __tablename__ = "household_members"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(60), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    height = db.Column(db.Float, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    activity_level = db.Column(db.String(20), nullable=False)
    goal = db.Column(db.String(20), nullable=False)
    daily_calories = db.Column(db.Integer, nullable=False)
    daily_protein = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    plan = db.Column(db.String(20), nullable=False)
    period = db.Column(db.String(10), nullable=False)  # month | year
    amount_paise = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), default="INR", nullable=False)
    order_id = db.Column(db.String(64), unique=True, nullable=False)
    payment_id = db.Column(db.String(64), unique=True)
    coupon_code = db.Column(db.String(30))
    discount_paise = db.Column(db.Integer, default=0, server_default="0", nullable=False)
    status = db.Column(db.String(20), default="created", nullable=False)  # created | paid | failed
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    paid_at = db.Column(db.DateTime)


class Coupon(db.Model):
    """Discount codes for festival offers and partnerships. Managed from /admin."""
    __tablename__ = "coupons"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)  # stored upper-case
    percent_off = db.Column(db.Integer, nullable=False)  # 1-90
    plans = db.Column(db.String(40), default="pro,family", nullable=False)  # which plans it applies to
    max_uses = db.Column(db.Integer)  # None = unlimited
    uses = db.Column(db.Integer, default=0, server_default="0", nullable=False)
    expires_at = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=True, server_default=true(), nullable=False)
    note = db.Column(db.String(120), default="", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class AIUsage(db.Model):
    """One row per successful AI food recognition (photo, voice or text), for daily limits."""
    __tablename__ = "ai_usage"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = db.Column(db.String(10), nullable=False)  # photo | voice | text
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
