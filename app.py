import os
import uuid
from functools import wraps
from datetime import datetime, timezone
from flask import Flask, render_template, redirect, url_for, flash, request, Response, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from forms import FollowUpForm, AdminActionForm, AdminLoginForm

app = Flask(__name__)

# --- SECURE CONFIGURATION ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'atu_admissions_hub_key_override_in_prod')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///atu_followups.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB limit

ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'atu2026')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
db = SQLAlchemy(app)


# --- DATABASE MODEL ---
class AdmissionFollowUp(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)  # --- NEW PHONE COLUMN ---
    reference_id = db.Column(db.String(50), nullable=False)
    program = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    document_filename = db.Column(db.String(255), nullable=True)

    status = db.Column(db.String(30), default='Pending')
    admin_response = db.Column(db.Text, nullable=True)

    date_submitted = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_updated = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc))


with app.app_context():
    db.create_all()


# --- SECURITY DECORATORS ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Staff access required. Please log in.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)

    return decorated_function


# --- PUBLIC ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/submit', methods=['GET', 'POST'])
def submit_ticket():
    form = FollowUpForm()
    if form.validate_on_submit():
        filename = None
        if form.document.data:
            file = form.document.data
            filename = f"{form.reference_id.data}_{uuid.uuid4().hex[:6]}_{secure_filename(file.filename)}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_followup = AdmissionFollowUp(
            full_name=form.full_name.data,
            phone=form.phone.data,  # --- CAPTURE PHONE DATA ---
            reference_id=form.reference_id.data.strip().upper(),
            program=form.program.data,
            message=form.message.data,
            document_filename=filename
        )
        db.session.add(new_followup)
        db.session.commit()

        flash(f'Follow-up submitted successfully! Use your Reference ID to track updates.', 'success')
        return redirect(url_for('track_gateway'))

    return render_template('submit.html', form=form)


@app.route('/track', methods=['GET', 'POST'])
def track_gateway():
    records = None
    search_id = None
    if request.method == 'POST':
        search_id = request.form.get('reference_id', '').strip().upper()
        records = AdmissionFollowUp.query.filter_by(reference_id=search_id).order_by(
            AdmissionFollowUp.date_submitted.desc()).all()
        if not records:
            flash(f'No records found for Reference ID: {search_id}', 'error')

    return render_template('track.html', records=records, search_id=search_id)


# --- SECURE ADMIN ROUTES ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    form = AdminLoginForm()
    if form.validate_on_submit():
        if form.username.data == ADMIN_USER and form.password.data == ADMIN_PASS:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials', 'error')
    return render_template('admin_login.html', form=form)


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    active_queue = AdmissionFollowUp.query.filter(
        AdmissionFollowUp.status.in_(['Pending', 'Action Required'])).order_by(
        AdmissionFollowUp.date_submitted.asc()).all()
    resolved_queue = AdmissionFollowUp.query.filter_by(status='Resolved').order_by(
        AdmissionFollowUp.last_updated.desc()).all()

    form = AdminActionForm()
    return render_template('admin_dashboard.html', active_queue=active_queue, resolved_queue=resolved_queue, form=form)


@app.route('/admin/process/<int:record_id>', methods=['POST'])
@admin_required
def admin_process(record_id):
    record = AdmissionFollowUp.query.get_or_404(record_id)
    form = AdminActionForm()

    if form.validate_on_submit():
        record.status = form.status.data
        if form.admin_response.data:
            record.admin_response = form.admin_response.data.strip()
        else:
            record.admin_response = None

        db.session.commit()
        flash(f'Record for {record.full_name} updated successfully.', 'success')
        return redirect(url_for('admin_dashboard'))

    flash('Error updating record.', 'error')
    return redirect(url_for('admin_dashboard'))


@app.route('/download/<filename>')
@admin_required
def download_document(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.errorhandler(413)
def request_entity_too_large(error):
    flash('File too large. Maximum upload size is 5MB.', 'error')
    return redirect(request.url), 413


if __name__ == '__main__':
    is_debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 't']
    app.run(debug=is_debug, host='0.0.0.0', port=5000)