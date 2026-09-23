from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, SubmitField, PasswordField
from wtforms.validators import DataRequired, Optional

class FollowUpForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired()])
    phone = StringField('Phone Number', validators=[DataRequired()])
    reference_id = StringField('Reference ID', validators=[DataRequired()])
    program = StringField('Program of Choice', validators=[DataRequired()])
    message = TextAreaField('What do you need help with?', validators=[DataRequired()])
    document = FileField('Upload Document (Optional)', validators=[
        Optional(),
        FileAllowed(['pdf', 'jpg', 'png', 'jpeg'], 'PDFs and Images only!')
    ])
    submit = SubmitField('Submit Follow-Up')

class AdminActionForm(FlaskForm):
    status = SelectField('Status', choices=[
        ('Pending', 'Pending (In Queue)'),
        ('Action Required', 'Action Required (Waiting on Student)'),
        ('Resolved', 'Resolved (Issue Closed)')
    ])
    admin_response = TextAreaField('Message to Student (Optional)', validators=[Optional()])
    submit = SubmitField('Save & Update')

class AdminLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Authenticate')