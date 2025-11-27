# 🧠 NextCareer — Smart Resume & Job Portal
NextCareer is a full-featured platform that helps **students** build, score, and manage resumes, while enabling **HRs** to post jobs, shortlist candidates, and schedule interviews with automated email notifications.

---
Features

 For Students:
- Create ATS-optimized resumes with multiple templates (Modern, Classic, Minimal)
- Auto-generate PDF resumes (using `xhtml2pdf`)
- Apply for jobs using built or uploaded resumes
- Get instant **ATS score** based on job requirements
- Track applications & feedback
- Role-based **Interview Preparation** feature (PYQs, important Qs)

 For HR:
- Post job openings and manage applicants
- Shortlist or reject candidates with email notifications
- Schedule interviews with built-in email integration

---

 Tech Stack

| Layer | Technology |
|-------|-------------|
| Backend | Django 5.2 |
| Frontend | HTML, CSS, Bootstrap |
| Database | SQLite / PostgreSQL |
| PDF Engine | xhtml2pdf (ReportLab) |
| Email | SMTP (Gmail App Password) |


## ⚙️ Setup Instructions

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/<your-username>/nexty.git
cd nexty

python -m venv venv
venv\Scripts\activate    # on Windows
# source venv/bin/activate  # on Mac/Linux

pip install -r requirements.txt

Apply Migrations
python manage.py makemigrations
python manage.py migrate

 Run the Server
python manage.py runserver


Email

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your_email@gmail.com'
EMAIL_HOST_PASSWORD = 'your_app_password'
