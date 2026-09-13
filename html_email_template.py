from datetime import datetime
from html import escape
from typing import Dict, List


def create_html_email(
    summary="",
    metrics: Dict = None,
    reports: List[str] = None,
    available_charts: List[str] = None,
    company_name="AI Sales Intelligence Platform"
):
    metrics = metrics or {}
    reports = reports or []
    available_charts = available_charts or []
    safe_summary = escape(str(summary or "")).replace("\n", "<br>")
    safe_company_name = escape(str(company_name))

    today = metrics.get("today", datetime.now().strftime("%B %d, %Y"))
    report_count = metrics.get("report_count", 0)
    chart_count = metrics.get("chart_count", 0)
    generated_at = metrics.get("generated_at", today)

    report_html = ""
    for rpt in reports:
        report_html += f"""
        <tr>
            <td style="
                padding:12px 18px;
                border-bottom:1px solid rgba(103,232,249,.14);
                color:#E2E8F0;
                font-size:15px;
            ">
                ✓ {escape(str(rpt))}
            </td>
        </tr>
        """

    chart_titles = {
        "sales_by_region": "Regional Sales Intelligence",
        "quarterly_performance": "Quarterly Growth Analysis",
        "product_performance": "Product Revenue Distribution",
        "marketing_roi": "Marketing ROI Performance",
        "channel_performance": "Channel Effectiveness"
    }

    chart_html = ""
    for cid in available_charts:
        title = chart_titles.get(cid, cid.replace("_", " ").title())
        chart_html += f"""
        <tr>
            <td style="padding:25px 50px;">
                <div style="
                    background:
                        linear-gradient(135deg, rgba(0,229,255,.12), rgba(255,255,255,.03)),
                        linear-gradient(180deg, #0B1220 0%, #070B12 100%);
                    border:1px solid rgba(0,229,255,.26);
                    border-radius:24px;
                    overflow:hidden;
                    box-shadow:0 0 34px rgba(0,229,255,.10);
                ">
                    <img
                        src="cid:{cid}"
                        style="
                            width:100%;
                            display:block;
                        "
                    >
                    <div style="padding:28px;">
                        <div style="
                            color:#67E8F9;
                            letter-spacing:3px;
                            font-size:11px;
                            text-transform:uppercase;
                            margin-bottom:12px;
                            text-shadow:0 0 12px rgba(103,232,249,.55);
                        ">
                            AI PERFORMANCE INSIGHT
                        </div>
                        <h2 style="
                            margin:0;
                            color:#FFFFFF;
                            font-size:32px;
                            font-family:Georgia,serif;
                            text-shadow:0 0 18px rgba(0,229,255,.18);
                        ">
                            {title}
                        </h2>
                        <p style="
                            color:#CBD5E1;
                            font-size:16px;
                            line-height:1.8;
                            margin-top:15px;
                        ">
                            AI-generated performance analysis,
                            anomaly detection, trend forecasting,
                            and business intelligence insights.
                        </p>
                    </div>
                </div>
            </td>
        </tr>
        """

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<title>AI Executive Report</title>
</head>

<body style="
margin:0;
padding:0;
background:#050505;
font-family:Arial,sans-serif;
">

<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="center">

<table
width="920"
cellpadding="0"
cellspacing="0"
border="0"
style="
background:
radial-gradient(circle at top left, rgba(153,27,27,.92) 0%, rgba(5,5,5,0) 38%),
radial-gradient(circle at bottom right, rgba(0,229,255,.95) 0%, rgba(5,5,5,0) 34%),
linear-gradient(135deg, #020617 0%, #050505 48%, #020617 100%);
border-radius:32px;
overflow:hidden;
"
>

<tr>
<td style="padding:80px 60px 50px 60px;">

<div style="
font-size:12px;
letter-spacing:5px;
text-transform:uppercase;
color:#67E8F9;
text-shadow:0 0 12px rgba(103,232,249,.55);
">
AI SALES & MARKETING INTELLIGENCE
</div>

<h1 style="
margin:20px 0;
font-size:72px;
line-height:1.05;
font-family:Georgia,serif;
font-weight:normal;
color:#FFFFFF;
text-shadow:
0 0 20px rgba(255,255,255,.10),
0 0 40px rgba(0,229,255,.28);
">
Executive Performance
Report
</h1>

<p style="
font-size:22px;
line-height:1.8;
color:#CBD5E1;
max-width:700px;
">
Production-grade AI analytics platform
transforming raw business data into
executive-ready intelligence.
</p>

</td>
</tr>

<tr>
<td style="padding:0 50px 40px 50px;">

<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>

<td width="33%" style="padding:10px;">
<div style="
background:linear-gradient(135deg, rgba(0,229,255,.14), rgba(255,255,255,.03));
border:1px solid rgba(0,229,255,.25);
border-radius:24px;
padding:28px;
box-shadow:0 0 26px rgba(0,229,255,.12);
">
<div style="
font-size:12px;
letter-spacing:3px;
color:#67E8F9;
text-shadow:0 0 10px rgba(103,232,249,.5);
">
REPORTS
</div>
<h2 style="
margin:15px 0 0 0;
font-size:42px;
color:#67E8F9;
text-shadow:
0 0 14px rgba(103,232,249,.65),
0 0 28px rgba(103,232,249,.25);
">
{report_count}
</h2>
</div>
</td>

<td width="33%" style="padding:10px;">
<div style="
background:linear-gradient(135deg, rgba(0,229,255,.14), rgba(255,255,255,.03));
border:1px solid rgba(0,229,255,.25);
border-radius:24px;
padding:28px;
box-shadow:0 0 26px rgba(0,229,255,.12);
">
<div style="
font-size:12px;
letter-spacing:3px;
color:#67E8F9;
text-shadow:0 0 10px rgba(103,232,249,.5);
">
CHARTS
</div>
<h2 style="
margin:15px 0 0 0;
font-size:42px;
color:#67E8F9;
text-shadow:
0 0 14px rgba(103,232,249,.65),
0 0 28px rgba(103,232,249,.25);
">
{chart_count}
</h2>
</div>
</td>

<td width="33%" style="padding:10px;">
<div style="
background:linear-gradient(135deg, rgba(0,229,255,.14), rgba(255,255,255,.03));
border:1px solid rgba(0,229,255,.25);
border-radius:24px;
padding:28px;
box-shadow:0 0 26px rgba(0,229,255,.12);
">
<div style="
font-size:12px;
letter-spacing:3px;
color:#67E8F9;
text-shadow:0 0 10px rgba(103,232,249,.5);
">
GENERATED
</div>
<h2 style="
margin:15px 0 0 0;
font-size:20px;
color:#FFFFFF;
text-shadow:0 0 12px rgba(0,229,255,.18);
">
{today}
</h2>
</div>
</td>

</tr>
</table>

</td>
</tr>

<tr>
<td style="padding:0 50px 40px 50px;">
<div style="
background:linear-gradient(135deg, rgba(0,229,255,.10), rgba(255,255,255,.02));
border:1px solid rgba(0,229,255,.20);
border-radius:24px;
padding:40px;
box-shadow:0 0 40px rgba(0,229,255,.08);
">
<div style="
font-size:12px;
letter-spacing:4px;
text-transform:uppercase;
color:#67E8F9;
margin-bottom:20px;
text-shadow:0 0 12px rgba(103,232,249,.55);
">
Executive Summary
</div>

<h2 style="
font-family:Georgia,serif;
font-size:42px;
font-weight:normal;
color:#FFFFFF;
margin-top:0;
text-shadow:0 0 18px rgba(0,229,255,.16);
">
AI Executive Intelligence Briefing
</h2>

<p style="
font-size:18px;
line-height:2;
color:#CBD5E1;
">
   {safe_summary if safe_summary else "AI-generated executive summary unavailable."}
</p>
</div>
</td>
</tr>

{chart_html}

<tr>
<td style="padding:30px 50px 60px 50px;">
<div style="
background:linear-gradient(135deg, rgba(0,229,255,.10), rgba(255,255,255,.02));
border:1px solid rgba(0,229,255,.20);
border-radius:24px;
padding:35px;
box-shadow:0 0 40px rgba(0,229,255,.08);
">
<div style="
font-size:12px;
letter-spacing:4px;
text-transform:uppercase;
color:#67E8F9;
margin-bottom:20px;
text-shadow:0 0 12px rgba(103,232,249,.55);
">
Attached Assets
</div>

<h2 style="
font-family:Georgia,serif;
font-size:36px;
font-weight:normal;
color:#FFFFFF;
margin-top:0;
text-shadow:0 0 18px rgba(0,229,255,.16);
">
Intelligence Reports
</h2>

<table width="100%" cellpadding="0" cellspacing="0" border="0">
{report_html}
</table>
</div>
</td>
</tr>

<tr>
<td style="
background:linear-gradient(90deg, #030303 0%, #07121D 50%, #030303 100%);
padding:60px;
text-align:center;
">
<h2 style="
font-family:Georgia,serif;
font-size:34px;
font-weight:normal;
color:#FFFFFF;
text-shadow:0 0 18px rgba(0,229,255,.18);
">
   {safe_company_name}
</h2>

<p style="
color:#94A3B8;
font-size:15px;
line-height:2;
">
Generated using Multi-Agent AI • RAG • Analytics Engine •
Business Intelligence • Automated Reporting
</p>

<p style="
color:#67E8F9;
font-size:12px;
text-shadow:0 0 10px rgba(103,232,249,.35);
">
Generated: {generated_at}
</p>

<p style="
color:#475569;
font-size:11px;
">
© {datetime.now().year} {safe_company_name}
</p>
</td>
</tr>

</table>

</td>
</tr>
</table>

</body>
</html>
"""

    return html
