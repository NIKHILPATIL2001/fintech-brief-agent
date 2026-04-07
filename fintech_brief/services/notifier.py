"""FinTech Brief — SMTP notifier with email-safe table layout."""

import html
import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_IMPACT_RULE  = {"HIGH": "#D64045", "MEDIUM": "#C8882A", "LOW": "#3A7D44"}
_IMPACT_LABEL = {"HIGH": "#D64045", "MEDIUM": "#C8882A", "LOW": "#3A7D44"}
_IMPACT_DOT   = {"HIGH": "#D64045", "MEDIUM": "#C8882A", "LOW": "#3A7D44"}

_CATEGORY_LABEL = {
    "Strategic Move":       "Strategic Moves",
    "Regulatory Update":    "Regulatory Updates",
    "Innovation Highlight": "Innovation",
    "Other":                "Other",
}

# Inline style constants
_BODY_FONT  = "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;"
_SERIF_FONT = "font-family:Georgia,'Times New Roman',serif;"


def _smtp_send(to_email: str, subject: str, html_body: str) -> None:
    host     = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port     = int(os.getenv("SMTP_PORT", "587"))
    sender   = os.getenv("SENDER_EMAIL", "")
    password = os.getenv("SENDER_PASSWORD", "")
    if not sender or not password:
        raise EnvironmentError("SENDER_EMAIL and SENDER_PASSWORD must be set in .env")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP(host, port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(sender, password)
        smtp.sendmail(sender, to_email, msg.as_string())
    logger.info("Briefing sent to %s via %s:%s", to_email, host, port)


# ── HTML building blocks ──────────────────────────────────────────────────────

def _wrap(inner: str) -> str:
    """Outer full-width table → centred 600px shell."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <meta name="x-apple-disable-message-reformatting"/>
  <style>
    body{{margin:0;padding:0;background:#EDEBE6;{_BODY_FONT}}}
    a{{color:#8B1A1A;text-decoration:none}}
    @media only screen and (max-width:620px){{
      .shell{{width:100%!important}}
      .pad{{padding-left:20px!important;padding-right:20px!important}}
      .headline{{font-size:15px!important}}
      .hide-sm{{display:none!important}}
    }}
  </style>
</head>
<body style="margin:0;padding:0;background:#EDEBE6;">
<table width="100%" cellpadding="0" cellspacing="0" role="presentation"
       style="background:#EDEBE6;">
  <tr><td align="center" style="padding:36px 12px 64px;">
    <table class="shell" width="600" cellpadding="0" cellspacing="0" role="presentation"
           style="background:#FAFAF8;border:1px solid #D6D3CC;width:600px;">
      {inner}
    </table>
  </td></tr>
</table>
</body>
</html>"""


def _masthead(date_esc: str, n: int) -> str:
    return f"""
    <tr><td class="pad" style="border-bottom:3px solid #1a1a1a;padding:28px 40px 0;">
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
        <tr>
          <td style="{_SERIF_FONT}font-size:24px;font-weight:700;color:#1a1a1a;
                     letter-spacing:-.02em;line-height:1;vertical-align:bottom;">
            FinTech Brief
          </td>
          <td align="right" style="vertical-align:bottom;">
            <div style="font-size:11px;font-weight:600;letter-spacing:.08em;
                        text-transform:uppercase;color:#1a1a1a;">{date_esc}</div>
            <div style="font-size:10px;color:#888;margin-top:3px;letter-spacing:.04em;">
              Morning Edition &nbsp;&middot;&nbsp; 9:00 AM
            </div>
          </td>
        </tr>
      </table>
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
             style="margin-top:14px;border-top:1px solid #1a1a1a;">
        <tr><td style="padding-top:10px;font-size:10px;letter-spacing:.1em;
                       text-transform:uppercase;color:#888;padding-bottom:0;">
          Strategic intelligence for financial services
          &nbsp;&middot;&nbsp; 24-hour scan &nbsp;&middot;&nbsp; {n} stories
        </td></tr>
      </table>
    </td></tr>"""


def _strip(stories: List[Dict]) -> str:
    high   = sum(1 for s in stories if str(s.get("impact","")).upper() == "HIGH")
    medium = sum(1 for s in stories if str(s.get("impact","")).upper() == "MEDIUM")
    low    = sum(1 for s in stories if str(s.get("impact","")).upper() == "LOW")
    lead   = html.escape((stories[0].get("title") or "")[:52])

    def stat(dot_color: str, label: str) -> str:
        return f"""<td style="padding-right:16px;white-space:nowrap;vertical-align:middle;">
          <table cellpadding="0" cellspacing="0" role="presentation">
            <tr>
              <td style="width:7px;height:7px;background:{dot_color};border-radius:50%;
                         vertical-align:middle;"></td>
              <td style="padding-left:6px;font-size:11px;color:#ccc;
                         vertical-align:middle;">{label}</td>
            </tr>
          </table>
        </td>"""

    stats = ""
    if high:   stats += stat("#D64045", f"{high}&nbsp;High")
    if medium: stats += stat("#C8882A", f"{medium}&nbsp;Medium")
    if low:    stats += stat("#3A7D44", f"{low}&nbsp;Low")

    return f"""
    <tr><td class="pad" style="background:#1a1a1a;padding:13px 40px;">
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
        <tr>
          <td style="font-size:9px;font-weight:600;letter-spacing:.15em;text-transform:uppercase;
                     color:#666;white-space:nowrap;vertical-align:middle;padding-right:16px;">
            This brief
          </td>
          <td style="width:1px;background:#333;padding:0;vertical-align:middle;">
            <div style="width:1px;height:14px;background:#333;"></div>
          </td>
          {stats}
          <td align="right" class="hide-sm"
              style="font-size:11px;color:#555;font-style:italic;
                     white-space:nowrap;overflow:hidden;vertical-align:middle;">
            Lead: {lead}
          </td>
        </tr>
      </table>
    </td></tr>"""


def _section_header(label: str) -> str:
    return f"""
    <tr><td class="pad" style="padding:32px 40px 0;">
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
        <tr><td style="font-size:9px;font-weight:600;letter-spacing:.18em;text-transform:uppercase;
                       color:#888;border-bottom:1px solid #D6D3CC;padding-bottom:10px;">
          {label}
        </td></tr>
      </table>
    </td></tr>"""


def _article_row(s: Dict, last: bool = False) -> str:
    impact      = str(s.get("impact", "MEDIUM")).upper()
    rule_color  = _IMPACT_RULE.get(impact, "#888")
    label_color = _IMPACT_LABEL.get(impact, "#888")
    impact_cap  = impact.capitalize() + " Impact"

    title  = html.escape(s.get("title",   "") or "")
    syn    = html.escape(s.get("synopsis","") or "")
    source = html.escape(s.get("source",  "") or "Unknown")
    link   = html.escape(s.get("link") or "#", quote=True)

    raw_ents = s.get("entities") or [s.get("firm", "")]
    if isinstance(raw_ents, str):
        raw_ents = [raw_ents]
    entity_cells = "".join(
        f'<td style="padding-right:4px;white-space:nowrap;">'
        f'<span style="font-size:10px;font-weight:500;letter-spacing:.04em;color:#777;'
        f'border:1px solid #D6D3CC;padding:2px 7px;text-transform:uppercase;">'
        f'{html.escape(str(e))}</span></td>'
        for e in raw_ents if e
    )

    border = "" if last else "border-bottom:1px solid #E8E5DF;"

    return f"""
    <tr><td class="pad" style="padding:18px 40px;{border}">
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation">

        <!-- meta row: rule + impact + source -->
        <tr>
          <td style="width:18px;vertical-align:middle;padding-right:10px;">
            <div style="width:18px;height:2px;background:{rule_color};"></div>
          </td>
          <td style="font-size:9px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;
                     color:{label_color};vertical-align:middle;">{impact_cap}</td>
          <td style="font-size:9px;color:#bbb;vertical-align:middle;padding:0 8px;">&middot;</td>
          <td style="font-size:10px;font-weight:500;letter-spacing:.06em;text-transform:uppercase;
                     color:#999;vertical-align:middle;">{source}</td>
        </tr>

        <!-- headline -->
        <tr><td colspan="4" style="padding-top:8px;">
          <a href="{link}" class="headline"
             style="font-size:16px;font-weight:600;color:#1a1a1a;text-decoration:none;
                    line-height:1.4;letter-spacing:-.01em;display:block;">
            {title}
          </a>
        </td></tr>

        <!-- synopsis -->
        <tr><td colspan="4" style="padding-top:8px;">
          <p style="margin:0;font-size:13px;font-weight:300;color:#444;line-height:1.75;">
            {syn}
          </p>
        </td></tr>

        <!-- footer: entities left, read right -->
        <tr><td colspan="4" style="padding-top:12px;">
          <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
            <tr>
              <td>
                <table cellpadding="0" cellspacing="0" role="presentation">
                  <tr>{entity_cells}</tr>
                </table>
              </td>
              <td align="right" style="white-space:nowrap;vertical-align:middle;">
                <a href="{link}"
                   style="font-size:11px;font-weight:500;color:#8B1A1A;
                          text-decoration:none;letter-spacing:.04em;">
                  Read &#8594;
                </a>
              </td>
            </tr>
          </table>
        </td></tr>

      </table>
    </td></tr>"""


def _footer_row(n: int, date_esc: str) -> str:
    return f"""
    <tr><td class="pad" style="border-top:3px solid #1a1a1a;padding:18px 40px;">
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
        <tr>
          <td style="{_SERIF_FONT}font-size:13px;font-weight:700;color:#1a1a1a;
                     vertical-align:middle;">
            FinTech Brief
          </td>
          <td align="right"
              style="font-size:10px;color:#999;letter-spacing:.03em;
                     line-height:1.7;vertical-align:middle;">
            {n} stories &middot; scored on impact, source &amp; relevance<br>
            Google News RSS &nbsp;+&nbsp; Claude &nbsp;+&nbsp; SMTP
          </td>
        </tr>
      </table>
    </td></tr>"""


# ── Public builders ───────────────────────────────────────────────────────────

def _build_empty_html(date_str: str) -> str:
    date_esc = html.escape(date_str)
    inner = f"""
    {_masthead(date_esc, 0)}
    <tr><td class="pad" style="padding:36px 40px;">
      <p style="margin:0;font-size:14px;font-weight:300;color:#555;line-height:1.8;">
        No qualifying fintech stories today after filters.<br>
        Share-price noise, conference announcements, and generic market
        headlines are excluded. You are caught up.
      </p>
    </td></tr>
    {_footer_row(0, date_esc)}"""
    return _wrap(inner)


def _build_html(stories: List[Dict], date_str: str) -> str:
    if not stories:
        return _build_empty_html(date_str)

    date_esc = html.escape(date_str)
    n = len(stories)

    categories: Dict[str, List[Dict]] = {}
    for s in stories:
        cat = s.get("category", "Other")
        categories.setdefault(cat, []).append(s)

    sections = ""
    for cat, cat_stories in categories.items():
        label = html.escape(_CATEGORY_LABEL.get(cat, cat))
        sections += _section_header(label)
        for i, s in enumerate(cat_stories):
            sections += _article_row(s, last=(i == len(cat_stories) - 1))

    inner = f"""
    {_masthead(date_esc, n)}
    {_strip(stories)}
    {sections}
    {_footer_row(n, date_esc)}"""

    return _wrap(inner)


# ── Public API ────────────────────────────────────────────────────────────────

def send_briefing(stories: List[Dict], recipient: str = None, mock: bool = False) -> bool:
    date_str  = datetime.now().strftime("%A, %B %d %Y")
    html_body = _build_html(stories, date_str)

    if mock:
        print(html_body)
        return True

    to_email = recipient or os.getenv("RECIPIENT_EMAIL")
    if not to_email:
        logger.error("No recipient email set. Set RECIPIENT_EMAIL in .env")
        return False

    subj = f"FinTech Brief — {date_str}"
    if not stories:
        subj += " (quiet day)"

    try:
        _smtp_send(to_email, subj, html_body)
        return True
    except EnvironmentError as e:
        logger.error("SMTP config missing: %s", e)
        return False
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP auth failed — check SENDER_EMAIL / SENDER_PASSWORD in .env")
        return False
    except smtplib.SMTPException as e:
        logger.error("SMTP error: %s", e)
        return False
    except OSError as e:
        logger.error("Network error: %s", e)
        return False
    except Exception as e:
        logger.exception("Email send failed: %s", e)
        return False
