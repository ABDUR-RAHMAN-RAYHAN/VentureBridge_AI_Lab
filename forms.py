from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, ValidationError
from models import User

IMG_EXT = ["png", "jpg", "jpeg"]


class RegisterForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(2, 120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=150)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField("Confirm Password",
                                      validators=[DataRequired(), EqualTo("password", message="Passwords must match.")])
    role = SelectField("I am a...", choices=[("founder", "Founder"), ("investor", "Investor"),
                                              ("jobseeker", "Job Seeker")], validators=[DataRequired()])

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower().strip()).first():
            raise ValidationError("An account with this email already exists.")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password")])


class ProfileForm(FlaskForm):
    photo = FileField("Profile Photo", validators=[Optional(), FileAllowed(IMG_EXT, "Images only.")])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    bio = TextAreaField("Bio", validators=[Optional(), Length(max=2000)])
    location = StringField("Location", validators=[Optional(), Length(max=120)])
    education = StringField("Education", validators=[Optional(), Length(max=255)])
    experience = StringField("Experience", validators=[Optional(), Length(max=255)])
    industry = StringField("Industry", validators=[Optional(), Length(max=120)])
    skills = StringField("Skills (comma-separated)", validators=[Optional(), Length(max=500)])
    interests = StringField("Interests (comma-separated)", validators=[Optional(), Length(max=500)])


class ContactForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    message = TextAreaField("Message", validators=[DataRequired(), Length(max=3000)])
