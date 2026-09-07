import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class EmailService:
    def __init__(self):
        self.enabled = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
        self.host = os.getenv("EMAIL_HOST", "smtp.gmail.com")
        self.port = int(os.getenv("EMAIL_PORT", "587"))
        self.username = os.getenv("EMAIL_USERNAME", "")
        self.password = os.getenv("EMAIL_PASSWORD", "")
        self.from_email = os.getenv("EMAIL_FROM", self.username)

    def _send_email(self, to_email: str, subject: str, body: str, html_body: str = None):
        if not self.enabled:
            logger.info(f"Email service disabled. Skipping email to {to_email}")
            return False

        if not self.username or not self.password:
            logger.error("Email credentials not configured. Cannot send email.")
            return False
            
        if not to_email or "@" not in to_email or "." not in to_email:
            logger.warning(f"Skipping email dispatch: '{to_email}' is not a valid recipient email address.")
            return False

        if html_body:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
        else:
            msg = MIMEMultipart()
            msg.attach(MIMEText(body, "plain"))

        msg["From"] = f"{self.from_email} <{self.username}>" if self.from_email and self.from_email != self.username else self.username
        msg["To"] = to_email
        msg["Subject"] = subject

        try:
            server = smtplib.SMTP(self.host, self.port)
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            logger.info(f"Successfully sent email to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def send_registration_email(self, to_email: str, student_name: str, username: str, password: str):
        subject = "Welcome to TIPS-G: Your Student Account Details"
        plain_body = f"""Dear {student_name},

Welcome to the TIPS-G Alwar Student Attendance System!

Your registration was successful. Please find your login credentials below:
Username: {username}
Password: {password}

Please keep this information secure. You can log in using the Desktop Application.

Regards,
TIPS-G Administration
"""
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to TIPS-G</title>
</head>
<body style="margin: 0; padding: 20px; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; line-height: 1.6;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);">
        <!-- Header Banner -->
        <tr>
            <td style="background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%); padding: 30px 24px; text-align: center; color: #ffffff;">
                <h1 style="margin: 0; font-size: 24px; font-weight: 800; letter-spacing: 0.5px;">TIPS-G ALWAR</h1>
                <p style="margin: 6px 0 0 0; font-size: 13px; color: #bfdbfe; font-weight: 500;">INSTITUTE OF PROFESSIONAL STUDIES &amp; TECHNOLOGY</p>
            </td>
        </tr>

        <!-- Body Content -->
        <tr>
            <td style="padding: 30px 28px;">
                <!-- Badge -->
                <div style="display: inline-block; padding: 6px 14px; background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 20px; font-size: 12px; font-weight: 700; color: #1d4ed8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 18px;">
                    🎓 Welcome — New Student Registration
                </div>

                <h2 style="margin: 0 0 16px 0; font-size: 20px; color: #0f172a; font-weight: 700;">
                    Welcome to TIPS-G Attendance System
                </h2>

                <p style="margin: 0 0 16px 0; font-size: 15px; color: #334155;">
                    Dear <strong>{student_name}</strong>,
                </p>

                <p style="margin: 0 0 20px 0; font-size: 14px; color: #475569;">
                    Your registration with the <strong>TIPS-G Alwar Student Attendance System</strong> has been completed successfully. Please find your login credentials below. Keep this information secure and do not share it with anyone.
                </p>

                <!-- Credentials Card -->
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 16px 20px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="6">
                                <tr>
                                    <td width="35%" style="font-size: 13px; color: #64748b; font-weight: 600;">Student Name:</td>
                                    <td width="65%" style="font-size: 14px; color: #0f172a; font-weight: 700;">{student_name}</td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b; font-weight: 600;">Username:</td>
                                    <td style="font-size: 14px; color: #1e3a8a; font-weight: 700;">{username}</td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b; font-weight: 600;">Password:</td>
                                    <td style="font-size: 14px; color: #1e3a8a; font-weight: 700;">{password}</td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b; font-weight: 600;">Login Via:</td>
                                    <td>
                                        <span style="display: inline-block; padding: 2px 10px; background-color: #dcfce7; color: #15803d; border-radius: 12px; font-size: 12px; font-weight: 700;">
                                            Desktop Application
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>

                <!-- Security Notice -->
                <div style="padding: 12px 16px; background-color: #fffbeb; border: 1px solid #fde68a; border-left: 4px solid #f59e0b; border-radius: 4px; margin-bottom: 16px;">
                    <p style="margin: 0; font-size: 13px; color: #92400e; font-weight: 600;">🔒 Security Notice</p>
                    <p style="margin: 4px 0 0 0; font-size: 13px; color: #78350f;">Please keep your login credentials secure and change your password after your first login. Do not share your credentials with anyone.</p>
                </div>

                <p style="margin: 20px 0 0 0; font-size: 14px; color: #334155; font-weight: 500;">
                    Welcome aboard — wishing you a productive academic journey!
                </p>
            </td>
        </tr>

        <!-- Footer -->
        <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 24px; text-align: center;">
                <p style="margin: 0; font-size: 12px; color: #64748b; font-weight: 600;">
                    TIPS-G Alwar Administration &bull; Office of Academic Affairs
                </p>
                <p style="margin: 6px 0 0 0; font-size: 11px; color: #94a3b8;">
                    This is an automated notification from the Student Attendance Management System.
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""
        return self._send_email(to_email, subject, plain_body, html_body)

    def send_absence_alert_email(self, parent_email: str, parent_name: str, student_name: str, date_str: str):
        subject = f"🚨 TIPS-G Absence Alert: {student_name} was Absent Today ({date_str})"
        recipient = parent_name or "Parent / Guardian"
        plain_body = f"""Dear {recipient},

This is an official notification from TIPS-G Alwar Administration.

Please be informed that your student, {student_name}, was marked ABSENT for today's classes ({date_str}).

ATTENDANCE RECORD:
• Student Name: {student_name}
• Date: {date_str}
• Status: ABSENT

[HINDI / हिंदी विवरण]
आदरणीय {recipient},

यह TIPS-G अलवर प्रशासन की ओर से एक आधिकारिक सूचना है।
आपको सूचित किया जाता है कि आपके छात्र/छात्रा {student_name} आज दिनांक {date_str} को संस्थान में अनुपस्थित (ABSENT) दर्ज किए गए हैं।

उपस्थिति विवरण:
• छात्र/छात्रा का नाम: {student_name}
• दिनांक: {date_str}
• उपस्थिति स्थिति: अनुपस्थित (ABSENT)

If your student had an urgent reason or medical emergency, please submit a leave application through the student portal or contact the institute administration office.

Regards,
TIPS-G Administration
"""
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Absence Alert</title>
</head>
<body style="margin: 0; padding: 20px; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; line-height: 1.6;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 620px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);">
        <!-- Header Banner -->
        <tr>
            <td style="background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%); padding: 28px 24px; text-align: center; color: #ffffff;">
                <h1 style="margin: 0; font-size: 24px; font-weight: 800; letter-spacing: 0.5px;">TIPS-G ALWAR</h1>
                <p style="margin: 6px 0 0 0; font-size: 13px; color: #bfdbfe; font-weight: 500;">INSTITUTE OF PROFESSIONAL STUDIES &amp; TECHNOLOGY</p>
            </td>
        </tr>

        <!-- Body Content -->
        <tr>
            <td style="padding: 30px 28px;">
                <!-- Absent Badge -->
                <div style="display: inline-block; padding: 6px 14px; background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 20px; font-size: 12px; font-weight: 700; color: #dc2626; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 18px;">
                    🚨 Absence Alert / अनुपस्थिति सूचना
                </div>

                <!-- ================= ENGLISH SECTION ================= -->
                <h2 style="margin: 0 0 14px 0; font-size: 20px; color: #0f172a; font-weight: 700;">
                    Student Absence Notification
                </h2>

                <p style="margin: 0 0 14px 0; font-size: 15px; color: #334155;">
                    Dear <strong>{recipient}</strong>,
                </p>

                <p style="margin: 0 0 18px 0; font-size: 14px; color: #475569;">
                    This is an official notification from <strong>TIPS-G Alwar Administration</strong>. Please be informed that your student, <strong>{student_name}</strong>, was marked <strong>ABSENT</strong> for today's classes.
                </p>

                <!-- English Details Card -->
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 16px;">
                    <tr>
                        <td style="padding: 14px 18px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="5">
                                <tr>
                                    <td width="35%" style="font-size: 13px; color: #64748b; font-weight: 600;">Student Name:</td>
                                    <td width="65%" style="font-size: 14px; color: #0f172a; font-weight: 700;">{student_name}</td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b; font-weight: 600;">Date:</td>
                                    <td style="font-size: 14px; color: #0f172a; font-weight: 600;">{date_str}</td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b; font-weight: 600;">Recorded Status:</td>
                                    <td>
                                        <span style="display: inline-block; padding: 2px 10px; background-color: #fee2e2; color: #991b1b; border-radius: 12px; font-size: 12px; font-weight: 700; border: 1px solid #fecaca;">
                                            ABSENT
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>

                <p style="margin: 0 0 20px 0; font-size: 13px; color: #64748b; line-height: 1.5;">
                    If your student had an urgent reason or medical emergency, please submit a leave application through the student portal or contact the institute administration office at the earliest.
                </p>

                <!-- Divider -->
                <div style="border-top: 2px dashed #cbd5e1; margin: 26px 0;"></div>

                <!-- ================= HINDI SECTION ================= -->
                <div style="display: inline-block; padding: 4px 12px; background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 14px; font-size: 12px; font-weight: 700; color: #166534; margin-bottom: 12px;">
                    🇮🇳 हिंदी विवरण / Hindi Version
                </div>

                <h3 style="margin: 0 0 12px 0; font-size: 18px; color: #0f172a; font-weight: 700;">
                    छात्र/छात्रा की अनुपस्थिति की सूचना
                </h3>

                <p style="margin: 0 0 12px 0; font-size: 15px; color: #334155;">
                    आदरणीय <strong>{recipient}</strong>,
                </p>

                <p style="margin: 0 0 16px 0; font-size: 14px; color: #475569;">
                    यह <strong>TIPS-G अलवर प्रशासन</strong> की ओर से एक आधिकारिक सूचना है। आपको सूचित किया जाता है कि आपके छात्र/छात्रा <strong>{student_name}</strong> आज दिनांक <strong>{date_str}</strong> को संस्थान में <strong>अनुपस्थित (ABSENT)</strong> दर्ज किए गए हैं।
                </p>

                <!-- Hindi Details Card -->
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 16px;">
                    <tr>
                        <td style="padding: 14px 18px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="5">
                                <tr>
                                    <td width="40%" style="font-size: 13px; color: #64748b; font-weight: 600;">छात्र/छात्रा का नाम:</td>
                                    <td width="60%" style="font-size: 14px; color: #0f172a; font-weight: 700;">{student_name}</td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b; font-weight: 600;">दिनांक:</td>
                                    <td style="font-size: 14px; color: #0f172a; font-weight: 600;">{date_str}</td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b; font-weight: 600;">दर्ज उपस्थिति:</td>
                                    <td>
                                        <span style="display: inline-block; padding: 2px 10px; background-color: #fee2e2; color: #991b1b; border-radius: 12px; font-size: 12px; font-weight: 700; border: 1px solid #fecaca;">
                                            अनुपस्थित (ABSENT)
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>

                <p style="margin: 0 0 20px 0; font-size: 13px; color: #64748b; line-height: 1.5;">
                    यदि छात्र की अनुपस्थिति किसी आपातकालीन कारण या चिकित्सा स्थिति के कारण हुई है, तो कृपया छात्र पोर्टल के माध्यम से अवकाश आवेदन प्रस्तुत करें अथवा संस्थान प्रशासन कार्यालय से शीघ्र संपर्क करें।
                </p>

                <p style="margin: 20px 0 0 0; font-size: 14px; color: #334155; font-weight: 500;">
                    धन्यवाद एवं सस्नेह नमस्कार।
                </p>
            </td>
        </tr>

        <!-- Footer -->
        <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 24px; text-align: center;">
                <p style="margin: 0; font-size: 12px; color: #64748b; font-weight: 600;">
                    TIPS-G Alwar Administration &bull; Office of Academic Affairs &amp; Student Discipline
                </p>
                <p style="margin: 4px 0 0 0; font-size: 11px; color: #64748b;">
                    TIPS-G अलवर प्रशासन &bull; शैक्षणिक एवं अनुशासन विभाग
                </p>
                <p style="margin: 8px 0 0 0; font-size: 11px; color: #94a3b8;">
                    This is an automated notification from the Student Attendance Management System.
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""
        return self._send_email(parent_email, subject, plain_body, html_body)

    def send_late_alert_email(
        self,
        to_email: str,
        student_name: str,
        arrival_time: str,
        date_str: str = None,
        date: str = None,
        recipient_name: str = "Parent / Guardian"
    ) -> bool:
        """
        Sends a bilingual (English & Hindi) late arrival alert email to parents/students
        using the branded TIPS-G template with clear visual indicators.
        """
        event_date = date_str or date or "Today"
        subject = f"⚠️ Late Arrival Alert: {student_name} marked LATE ({event_date}) — TIPS-G Alwar"

        plain_body = f"""Dear {recipient_name},

==================================================
OFFICIAL NOTICE: STUDENT LATE ARRIVAL (विलंब आगमन)
==================================================

[ENGLISH]
This is an official attendance alert from TIPS-G Alwar Administration.
Please be informed that your student, {student_name}, arrived late to the institute today ({event_date}).

ATTENDANCE RECORD:
• Student Name: {student_name}
• Date: {event_date}
• Check-in Time: {arrival_time}
• Status: LATE (देर से आगमन)

Punctuality is essential for academic discipline and uninterrupted learning. We request parents and guardians to discuss this with the student to ensure timely arrival in future classes. If there was a genuine emergency or transport delay, please inform the institute administration.

--------------------------------------------------
[HINDI / हिंदी विवरण]
आदरणीय {recipient_name},

यह TIPS-G अलवर प्रशासन की ओर से एक आधिकारिक उपस्थिति सूचना है।
आपको सूचित किया जाता है कि आपके छात्र/छात्रा {student_name} आज दिनांक {event_date} को संस्थान में निर्धारित समय के उपरांत {arrival_time} बजे पहुंचे हैं, और उनकी उपस्थिति LATE (विलंब) दर्ज की गई है।

उपस्थिति विवरण:
• छात्र/छात्रा का नाम: {student_name}
• दिनांक: {event_date}
• आगमन समय: {arrival_time}
• उपस्थिति स्थिति: देर से आगमन (LATE)

छात्र के बेहतर शैक्षणिक भविष्य और अनुशासन के लिए समय की पाबंदी अनिवार्य है। कृपया सुनिश्चित करें कि छात्र आगामी दिनों में समय पर संस्थान पहुंचे। किसी आपात स्थिति या कारण की जानकारी संस्थान कार्यालय को अवश्य दें।

Warm regards / सस्नेह धन्यवाद,
TIPS-G Alwar Administration / TIPS-G अलवर प्रशासन
Office of Academic Affairs & Student Discipline
"""

        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Late Arrival Alert</title>
</head>
<body style="margin: 0; padding: 20px; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; line-height: 1.6;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 620px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);">
        <!-- Header Banner -->
        <tr>
            <td style="background: linear-gradient(135deg, #7c2d12 0%, #c2410c 50%, #ea580c 100%); padding: 28px 24px; text-align: center; color: #ffffff;">
                <h1 style="margin: 0; font-size: 24px; font-weight: 800; letter-spacing: 0.5px;">TIPS-G ALWAR</h1>
                <p style="margin: 6px 0 0 0; font-size: 13px; color: #ffedd5; font-weight: 500;">INSTITUTE OF PROFESSIONAL STUDIES &amp; TECHNOLOGY</p>
            </td>
        </tr>

        <!-- Main Body -->
        <tr>
            <td style="padding: 30px 28px;">
                <!-- Late Badge -->
                <div style="display: inline-block; padding: 6px 14px; background-color: #fff7ed; border: 1px solid #fed7aa; border-radius: 20px; font-size: 12px; font-weight: 700; color: #c2410c; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 18px;">
                    ⚠️ Late Arrival Alert / विलंब आगमन सूचना
                </div>

                <!-- ================= ENGLISH SECTION ================= -->
                <h2 style="margin: 0 0 14px 0; font-size: 20px; color: #0f172a; font-weight: 700;">
                    Student Late Arrival Notification
                </h2>

                <p style="margin: 0 0 14px 0; font-size: 15px; color: #334155;">
                    Dear <strong>{recipient_name}</strong>,
                </p>

                <p style="margin: 0 0 18px 0; font-size: 14px; color: #475569;">
                    This is an official notification from <strong>TIPS-G Alwar Administration</strong>. Please be informed that your student, <strong>{student_name}</strong>, arrived late to the institute today and checked in after the scheduled commencement time.
                </p>

                <!-- English Details Card -->
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 16px;">
                    <tr>
                        <td style="padding: 14px 18px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="5">
                                <tr>
                                    <td width="35%" style="font-size: 13px; color: #64748b; font-weight: 600;">Student Name:</td>
                                    <td width="65%" style="font-size: 14px; color: #0f172a; font-weight: 700;">{student_name}</td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b; font-weight: 600;">Date:</td>
                                    <td style="font-size: 14px; color: #0f172a; font-weight: 600;">{event_date}</td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b; font-weight: 600;">Arrival Time:</td>
                                    <td style="font-size: 14px; color: #c2410c; font-weight: 700;">{arrival_time}</td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b; font-weight: 600;">Recorded Status:</td>
                                    <td>
                                        <span style="display: inline-block; padding: 2px 10px; background-color: #ffedd5; color: #9a3412; border-radius: 12px; font-size: 12px; font-weight: 700; border: 1px solid #fed7aa;">
                                            LATE ARRIVAL
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>

                <p style="margin: 0 0 20px 0; font-size: 13px; color: #64748b; line-height: 1.5;">
                    Punctuality is essential for academic discipline and steady learning. We kindly request parents and guardians to ensure timely departures from home. If this was caused by an unavoidable emergency or transport issue, please inform the administration office.
                </p>

                <!-- Divider -->
                <div style="border-top: 2px dashed #cbd5e1; margin: 26px 0;"></div>

                <!-- ================= HINDI SECTION ================= -->
                <div style="display: inline-block; padding: 4px 12px; background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 14px; font-size: 12px; font-weight: 700; color: #166534; margin-bottom: 12px;">
                    🇮🇳 हिंदी विवरण / Hindi Version
                </div>

                <h3 style="margin: 0 0 12px 0; font-size: 18px; color: #0f172a; font-weight: 700;">
                    छात्र/छात्रा के विलंब से आगमन की सूचना
                </h3>

                <p style="margin: 0 0 12px 0; font-size: 15px; color: #334155;">
                    आदरणीय <strong>{recipient_name}</strong>,
                </p>

                <p style="margin: 0 0 16px 0; font-size: 14px; color: #475569;">
                    यह <strong>TIPS-G अलवर प्रशासन</strong> की ओर से एक आधिकारिक सूचना है। आपको सूचित किया जाता है कि आपके छात्र/छात्रा <strong>{student_name}</strong> आज दिनांक <strong>{event_date}</strong> को निर्धारित समय के उपरांत <strong>{arrival_time}</strong> बजे संस्थान पहुंचे हैं, तथा उनकी उपस्थिति <strong>LATE (विलंब)</strong> दर्ज की गई है।
                </p>

                <!-- Hindi Details Card -->
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 16px;">
                    <tr>
                        <td style="padding: 14px 18px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="5">
                                <tr>
                                    <td width="40%" style="font-size: 13px; color: #64748b; font-weight: 600;">छात्र/छात्रा का नाम:</td>
                                    <td width="60%" style="font-size: 14px; color: #0f172a; font-weight: 700;">{student_name}</td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b; font-weight: 600;">दिनांक:</td>
                                    <td style="font-size: 14px; color: #0f172a; font-weight: 600;">{event_date}</td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b; font-weight: 600;">आगमन का समय:</td>
                                    <td style="font-size: 14px; color: #c2410c; font-weight: 700;">{arrival_time}</td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b; font-weight: 600;">दर्ज उपस्थिति:</td>
                                    <td>
                                        <span style="display: inline-block; padding: 2px 10px; background-color: #fee2e2; color: #991b1b; border-radius: 12px; font-size: 12px; font-weight: 700; border: 1px solid #fecaca;">
                                            देर से आगमन (LATE)
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>

                <p style="margin: 0 0 20px 0; font-size: 13px; color: #64748b; line-height: 1.5;">
                    शैक्षणिक अनुशासन एवं नियमित अध्ययन हेतु समय की पाबंदी अत्यंत आवश्यक है। कृपया छात्र को समय पर संस्थान पहुंचने हेतु निर्देशित करें। किसी विशेष समस्या अथवा आपातकालीन स्थिति की जानकारी संस्थान कार्यालय को अवश्य प्रदान करें।
                </p>

                <p style="margin: 20px 0 0 0; font-size: 14px; color: #334155; font-weight: 500;">
                    धन्यवाद एवं सस्नेह नमस्कार।
                </p>
            </td>
        </tr>

        <!-- Footer -->
        <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 24px; text-align: center;">
                <p style="margin: 0; font-size: 12px; color: #64748b; font-weight: 600;">
                    TIPS-G Alwar Administration &bull; Office of Academic Affairs &amp; Student Discipline
                </p>
                <p style="margin: 4px 0 0 0; font-size: 11px; color: #64748b;">
                    TIPS-G अलवर प्रशासन &bull; शैक्षणिक एवं अनुशासन विभाग
                </p>
                <p style="margin: 8px 0 0 0; font-size: 11px; color: #94a3b8;">
                    This is an automated notification from the Student Attendance Management System.
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""
        return self._send_email(to_email, subject, plain_body, html_body)


    def send_password_reset_otp(self, to_email: str, student_name: str, otp_code: str):
        subject = "TIPS-G Password Reset OTP"
        body = f"""Dear {student_name},

A password reset request was received for your account.

Your OTP code is: {otp_code}

This code will expire in 10 minutes.

If you did not request this reset, please contact the administration immediately.

Regards,
TIPS-G Administration
"""
        return self._send_email(to_email, subject, body)

    def send_email_verification_otp(self, to_email: str, student_name: str, otp_code: str):
        subject = "TIPS-G Email Verification OTP"
        plain_body = f"""Dear {student_name},

Thank you for registering with TIPS-G Student Attendance System.

Your 6-digit Email Verification OTP is: {otp_code}

This verification code will expire in 10 minutes. Please enter this code in the application to verify your Gmail address and account.

Regards,
TIPS-G Administration
"""
        html_body = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; background-color: #f8fafc; padding: 20px; color: #1e293b;">
    <div style="max-width: 500px; margin: auto; background: #ffffff; border-radius: 12px; padding: 24px; border: 1px solid #e2e8f0;">
        <h2 style="color: #4f46e5; margin-top: 0;">TIPS-G Email Verification</h2>
        <p>Dear <strong>{student_name}</strong>,</p>
        <p>Please enter the following 6-digit One-Time Password (OTP) to verify your Gmail account:</p>
        <div style="background: #f1f5f9; padding: 16px; border-radius: 8px; text-align: center; margin: 20px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #4f46e5;">{otp_code}</span>
        </div>
        <p style="font-size: 13px; color: #64748b;">This OTP is valid for 10 minutes. If you did not request this verification, please ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
        <p style="font-size: 12px; color: #94a3b8; margin-bottom: 0;">TIPS-G Alwar Student Attendance AI System</p>
    </div>
</body>
</html>
"""
        return self._send_email(to_email, subject, plain_body, html_body)


    def send_holiday_announcement_email(
        self,
        to_email: str,
        student_name: str,
        holiday_name: str,
        holiday_date_str: str,
        resume_date_str: str,
        description: str = ""
    ) -> bool:
        """
        Sends an official, branded holiday announcement email to a student via SMTP.
        Includes both rich HTML layout and plain text fallback.
        """
        subject = f"🎉 Holiday Announcement: {holiday_name} ({holiday_date_str}) — TIPS-G Alwar"
        
        desc_plain = f"\nAdditional Notes: {description}\n" if description else ""
        
        plain_body = f"""Dear {student_name},

This is an official announcement from TIPS-G Alwar Administration.

Please be informed that the institute will remain CLOSED on {holiday_date_str} on account of:
🎉 {holiday_name}

HOLIDAY DETAILS:
• Holiday Date: {holiday_date_str}
• Occasion: {holiday_name}
• Campus Status: CLOSED
• Classes Resume: {resume_date_str}
{desc_plain}
All regular academic lectures, laboratory practicals, and institutional operations will remain suspended on this date. Classes will resume as per regular schedule on {resume_date_str}.

Wishing you a joyful and safe holiday!

Warm regards,
TIPS-G Alwar Administration
Office of Academic Affairs
"""

        desc_html = f"""
        <div style="margin-top: 15px; padding: 12px 16px; background-color: #f8fafc; border-left: 4px solid #3b82f6; border-radius: 4px;">
            <p style="margin: 0; font-size: 13px; color: #475569;"><strong>Notes / Instructions:</strong> {description}</p>
        </div>
        """ if description else ""

        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Holiday Announcement</title>
</head>
<body style="margin: 0; padding: 20px; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; line-height: 1.6;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);">
        <!-- Header -->
        <tr>
            <td style="background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%); padding: 30px 24px; text-align: center; color: #ffffff;">
                <h1 style="margin: 0; font-size: 24px; font-weight: 800; letter-spacing: 0.5px;">TIPS-G ALWAR</h1>
                <p style="margin: 6px 0 0 0; font-size: 13px; color: #bfdbfe; font-weight: 500;">INSTITUTE OF PROFESSIONAL STUDIES &amp; TECHNOLOGY</p>
            </td>
        </tr>

        <!-- Body Content -->
        <tr>
            <td style="padding: 30px 28px;">
                <!-- Badge -->
                <div style="display: inline-block; padding: 6px 14px; background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 20px; font-size: 12px; font-weight: 700; color: #1d4ed8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 18px;">
                    🎉 Official Holiday Notice
                </div>

                <h2 style="margin: 0 0 16px 0; font-size: 20px; color: #0f172a; font-weight: 700;">
                    Institute Closure: {holiday_name}
                </h2>

                <p style="margin: 0 0 16px 0; font-size: 15px; color: #334155;">
                    Dear <strong>{student_name}</strong>,
                </p>

                <p style="margin: 0 0 20px 0; font-size: 14px; color: #475569;">
                    Please be informed that <strong>TIPS-G Alwar</strong> will remain <strong>CLOSED</strong> on <strong>{holiday_date_str}</strong> on account of <strong>{holiday_name}</strong>.
                </p>

                <!-- Details Card -->
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 16px 20px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="6">
                                <tr>
                                    <td width="35%" style="font-size: 13px; color: #64748b; font-weight: 600;">Holiday Event:</td>
                                    <td width="65%" style="font-size: 14px; color: #0f172a; font-weight: 700;">{holiday_name}</td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b; font-weight: 600;">Closure Date:</td>
                                    <td style="font-size: 14px; color: #0f172a; font-weight: 600;">{holiday_date_str}</td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b; font-weight: 600;">Campus Status:</td>
                                    <td>
                                        <span style="display: inline-block; padding: 2px 10px; background-color: #fee2e2; color: #dc2626; border-radius: 12px; font-size: 12px; font-weight: 700;">
                                            CLOSED
                                        </span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b; font-weight: 600;">Classes Resume:</td>
                                    <td>
                                        <span style="display: inline-block; padding: 2px 10px; background-color: #dcfce7; color: #15803d; border-radius: 12px; font-size: 12px; font-weight: 700;">
                                            {resume_date_str}
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>

                {desc_html}

                <p style="margin: 20px 0 0 0; font-size: 13px; color: #64748b; line-height: 1.5;">
                    All academic lectures, laboratory practicals, and administrative services will remain closed during this period. Normal operations and classes will resume on <strong>{resume_date_str}</strong>.
                </p>

                <p style="margin: 20px 0 0 0; font-size: 14px; color: #334155; font-weight: 500;">
                    Have a safe and restful holiday!
                </p>
            </td>
        </tr>

        <!-- Footer -->
        <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 24px; text-align: center;">
                <p style="margin: 0; font-size: 12px; color: #64748b; font-weight: 600;">
                    TIPS-G Alwar Administration &bull; Office of Academic Affairs
                </p>
                <p style="margin: 6px 0 0 0; font-size: 11px; color: #94a3b8;">
                    This is an automated notification from the Student Attendance Management System.
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""
        return self._send_email(to_email, subject, plain_body, html_body)

    def broadcast_holiday_email_to_students(
        self,
        students: list,
        holiday_name: str,
        holiday_date_str: str,
        resume_date_str: str,
        description: str = ""
    ) -> int:
        """
        Broadcasts the holiday announcement email via SMTP to all active students in the list.
        Runs safely over the recipients and logs success/failure counts.
        """
        if not self.enabled:
            logger.info("Email service disabled in settings. Skipping holiday email broadcast.")
            return 0

        logger.info(f"Starting SMTP holiday email broadcast for '{holiday_name}' on {holiday_date_str} to {len(students)} recipient(s)...")
        success_count = 0

        for s in students:
            email = s.get("email") if isinstance(s, dict) else getattr(s, "email", None)
            name = s.get("name") if isinstance(s, dict) else (getattr(s, "full_name", None) or getattr(s, "name", "Student"))

            if not email or "@" not in email:
                continue

            try:
                sent = self.send_holiday_announcement_email(
                    to_email=email,
                    student_name=name,
                    holiday_name=holiday_name,
                    holiday_date_str=holiday_date_str,
                    resume_date_str=resume_date_str,
                    description=description
                )
                if sent:
                    success_count += 1
            except Exception as e:
                logger.error(f"Failed to dispatch holiday email to {email}: {e}")

        logger.info(f"✓ Holiday SMTP broadcast completed. Successfully delivered to {success_count}/{len(students)} student(s).")
        return success_count

    def send_leave_request_notification(
        self,
        to_email: str,
        admin_name: str,
        student_name: str,
        registration_number: str,
        start_date: str,
        end_date: str,
        reason: str,
        leave_type: str = "Academic"
    ) -> bool:
        """Sends an email to Admin/Teacher when a student submits a new leave request."""
        subject = f"📋 New Student Leave Request: {student_name} ({registration_number})"
        plain_body = f"""Dear {admin_name},

A new student leave request has been submitted for your review:

Student Name: {student_name}
Registration No: {registration_number}
Leave Period: {start_date} to {end_date}
Leave Type: {leave_type}
Reason: {reason}

Please log into the TIPS-G Attendance System Desktop Dashboard to review and approve or reject this request.

Regards,
TIPS-G Alwar Administration
"""
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>New Leave Request</title>
</head>
<body style="margin: 0; padding: 20px; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; line-height: 1.6;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
        <tr>
            <td style="background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%); padding: 26px 24px; text-align: center; color: #ffffff;">
                <h1 style="margin: 0; font-size: 22px; font-weight: 800;">TIPS-G ALWAR</h1>
                <p style="margin: 4px 0 0 0; font-size: 12px; color: #bfdbfe; font-weight: 500;">STUDENT ATTENDANCE &amp; LEAVE PORTAL</p>
            </td>
        </tr>
        <tr>
            <td style="padding: 28px 24px;">
                <div style="display: inline-block; padding: 5px 12px; background-color: #fef3c7; border: 1px solid #fde68a; border-radius: 16px; font-size: 11px; font-weight: 700; color: #b45309; text-transform: uppercase; margin-bottom: 16px;">
                    ⏳ Pending Review — Student Leave
                </div>
                <h2 style="margin: 0 0 14px 0; font-size: 18px; color: #0f172a; font-weight: 700;">
                    New Leave Request Submitted
                </h2>
                <p style="margin: 0 0 18px 0; font-size: 14px; color: #475569;">
                    Dear <strong>{admin_name}</strong>, a student has applied for leave and requires administrative review.
                </p>
                <table style="width: 100%; border-collapse: collapse; background-color: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 20px;">
                    <tr><td style="padding: 10px 14px; font-size: 13px; color: #64748b; font-weight: 600; width: 140px; border-bottom: 1px solid #e2e8f0;">Student:</td><td style="padding: 10px 14px; font-size: 13px; color: #0f172a; font-weight: 700; border-bottom: 1px solid #e2e8f0;">{student_name} ({registration_number})</td></tr>
                    <tr><td style="padding: 10px 14px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #e2e8f0;">Duration:</td><td style="padding: 10px 14px; font-size: 13px; color: #1e3a8a; font-weight: 700; border-bottom: 1px solid #e2e8f0;">{start_date} to {end_date}</td></tr>
                    <tr><td style="padding: 10px 14px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #e2e8f0;">Type:</td><td style="padding: 10px 14px; font-size: 13px; color: #0f172a; border-bottom: 1px solid #e2e8f0;">{leave_type}</td></tr>
                    <tr><td style="padding: 10px 14px; font-size: 13px; color: #64748b; font-weight: 600;">Reason:</td><td style="padding: 10px 14px; font-size: 13px; color: #334155;">{reason}</td></tr>
                </table>
                <p style="margin: 0; font-size: 13px; color: #64748b;">
                    Please open the desktop app and go to the <strong>Leave Approvals</strong> tab to approve or reject this request.
                </p>
            </td>
        </tr>
        <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px 24px; text-align: center;">
                <p style="margin: 0; font-size: 11px; color: #94a3b8;">TIPS-G Alwar Administration &bull; Automated Leave Notification</p>
            </td>
        </tr>
    </table>
</body>
</html>"""
        return self._send_email(to_email, subject, plain_body, html_body)

    def send_leave_decision_notification(
        self,
        to_email: str,
        student_name: str,
        registration_number: str,
        start_date: str,
        end_date: str,
        status: str,
        remarks: str = ""
    ) -> bool:
        """Sends an email to Student/Parent when a leave request is Approved or Rejected."""
        is_approved = status.lower() == "approved"
        status_text = "Approved ✅" if is_approved else "Rejected ❌"
        status_color = "#15803d" if is_approved else "#b91c1c"
        badge_bg = "#dcfce7" if is_approved else "#fee2e2"
        badge_border = "#86efac" if is_approved else "#fca5a5"

        subject = f"Leave Request {status.upper()}: {student_name} ({start_date} - {end_date})"
        plain_body = f"""Dear {student_name},

Your leave request for the period {start_date} to {end_date} has been {status.upper()} by the administration.

Status: {status}
Student: {student_name} ({registration_number})
Period: {start_date} to {end_date}
{f'Remarks: {remarks}' if remarks else ''}

Regards,
TIPS-G Alwar Administration
"""
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Leave Request Decision</title>
</head>
<body style="margin: 0; padding: 20px; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; line-height: 1.6;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
        <tr>
            <td style="background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%); padding: 26px 24px; text-align: center; color: #ffffff;">
                <h1 style="margin: 0; font-size: 22px; font-weight: 800;">TIPS-G ALWAR</h1>
                <p style="margin: 4px 0 0 0; font-size: 12px; color: #bfdbfe; font-weight: 500;">INSTITUTE OF PROFESSIONAL STUDIES &amp; TECHNOLOGY</p>
            </td>
        </tr>
        <tr>
            <td style="padding: 28px 24px;">
                <div style="display: inline-block; padding: 6px 14px; background-color: {badge_bg}; border: 1px solid {badge_border}; border-radius: 16px; font-size: 12px; font-weight: 800; color: {status_color}; text-transform: uppercase; margin-bottom: 16px;">
                    {status_text}
                </div>
                <h2 style="margin: 0 0 14px 0; font-size: 18px; color: #0f172a; font-weight: 700;">
                    Leave Request Update
                </h2>
                <p style="margin: 0 0 18px 0; font-size: 14px; color: #475569;">
                    Dear <strong>{student_name}</strong>, your leave application has been processed by the institute administration.
                </p>
                <table style="width: 100%; border-collapse: collapse; background-color: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 20px;">
                    <tr><td style="padding: 10px 14px; font-size: 13px; color: #64748b; font-weight: 600; width: 130px; border-bottom: 1px solid #e2e8f0;">Status:</td><td style="padding: 10px 14px; font-size: 14px; color: {status_color}; font-weight: 800; border-bottom: 1px solid #e2e8f0;">{status.upper()}</td></tr>
                    <tr><td style="padding: 10px 14px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #e2e8f0;">Registration ID:</td><td style="padding: 10px 14px; font-size: 13px; color: #0f172a; border-bottom: 1px solid #e2e8f0;">{registration_number}</td></tr>
                    <tr><td style="padding: 10px 14px; font-size: 13px; color: #64748b; font-weight: 600;">Leave Period:</td><td style="padding: 10px 14px; font-size: 13px; color: #1e3a8a; font-weight: 700;">{start_date} to {end_date}</td></tr>
                </table>
                <p style="margin: 0; font-size: 13px; color: #64748b;">
                    {'Your attendance records for the approved dates will reflect as Leave.' if is_approved else 'If you have any questions, please contact the administration department.'}
                </p>
            </td>
        </tr>
        <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px 24px; text-align: center;">
                <p style="margin: 0; font-size: 11px; color: #94a3b8;">TIPS-G Alwar Administration &bull; Automated Leave Notification</p>
            </td>
        </tr>
    </table>
</body>
</html>"""
        return self._send_email(to_email, subject, plain_body, html_body)

email_service = EmailService()

