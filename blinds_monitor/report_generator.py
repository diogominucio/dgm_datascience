"""Generate executive competitor analysis reports and send via email."""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, FileSystemLoader

from config import (
    RECIPIENT_EMAIL,
    REPORTS_DIR,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SERVER,
    SMTP_USERNAME,
)

logger = logging.getLogger(__name__)


def generate_insights(analysis: dict) -> list[dict]:
    """Generate AI-like analyst insights from the data."""
    insights = []

    # Insight: Price movement summary
    price_changes = analysis.get("price_changes", [])
    if price_changes:
        increases = [c for c in price_changes if c["direction"] == "increase"]
        decreases = [c for c in price_changes if c["direction"] == "decrease"]

        if increases:
            avg_increase = sum(c["change_pct"] for c in increases) / len(increases)
            top_increase = increases[0]
            insights.append({
                "title": "⚠️ Alerta de Aumento de Preços",
                "text": (
                    f"Detectados {len(increases)} aumentos de preço desde a última coleta. "
                    f"O aumento médio foi de {avg_increase:.1f}%. "
                    f"O maior aumento foi no produto \"{top_increase['product']}\" "
                    f"({top_increase['category']}) com variação de "
                    f"+{top_increase['change_pct']}% "
                    f"(${top_increase['previous_price']:.2f} → "
                    f"${top_increase['current_price']:.2f}). "
                    "Isso pode indicar ajuste sazonal ou redução de promoções."
                ),
            })

        if decreases:
            avg_decrease = sum(c["change_pct"] for c in decreases) / len(decreases)
            top_decrease = decreases[0]
            insights.append({
                "title": "✅ Oportunidade: Reduções de Preço",
                "text": (
                    f"Identificadas {len(decreases)} reduções de preço. "
                    f"A redução média foi de {abs(avg_decrease):.1f}%. "
                    f"O produto com maior queda foi \"{top_decrease['product']}\" "
                    f"({top_decrease['category']}) com "
                    f"{top_decrease['change_pct']}% "
                    f"(${top_decrease['previous_price']:.2f} → "
                    f"${top_decrease['current_price']:.2f}). "
                    "Pode indicar início de campanha promocional ou liquidação."
                ),
            })

    # Insight: Promotion analysis
    promos = analysis.get("promotions", {})
    active_count = promos.get("total_promo_products_today", 0)
    if active_count > 0:
        insights.append({
            "title": "🏷️ Análise de Promoções",
            "text": (
                f"Atualmente existem {active_count} produtos com promoções ativas "
                f"no site blinds.com. A presença significativa de promoções sugere "
                f"que o concorrente está em fase de campanha agressiva de vendas. "
                f"Recomenda-se monitorar se essas promoções são temporárias ou "
                f"representam um ajuste permanente na estratégia de preços."
            ),
        })

    # Insight: Category analysis
    categories = analysis.get("categories", {})
    if categories:
        # Find category with highest discount
        max_discount_cat = max(
            categories.items(),
            key=lambda x: x[1].get("avg_discount_pct") or 0,
        )
        if max_discount_cat[1].get("avg_discount_pct"):
            insights.append({
                "title": "📊 Categoria Mais Agressiva em Preço",
                "text": (
                    f"A categoria \"{max_discount_cat[0]}\" apresenta o maior "
                    f"desconto médio: {max_discount_cat[1]['avg_discount_pct']:.1f}% "
                    f"abaixo do MSRP. Com preço médio de "
                    f"${max_discount_cat[1]['avg_price']:.2f} "
                    f"(MSRP médio: ${max_discount_cat[1]['avg_msrp']:.2f}), "
                    f"esta categoria demonstra a maior pressão competitiva. "
                    f"Isso pode representar uma tentativa de ganhar market share "
                    f"ou liquidar estoque."
                ),
            })

        # Find cheapest entry point
        min_price_cat = min(
            categories.items(),
            key=lambda x: x[1].get("min_price") or float("inf"),
        )
        if min_price_cat[1].get("min_price"):
            insights.append({
                "title": "💡 Ponto de Entrada Mais Acessível",
                "text": (
                    f"O produto mais barato disponível está na categoria "
                    f"\"{min_price_cat[0]}\" a ${min_price_cat[1]['min_price']:.2f}. "
                    f"Este price point é estrategicamente importante pois define "
                    f"o nível de entrada do mercado para consumidores price-sensitive."
                ),
            })

    # Insight: Weekly/monthly patterns
    weekly = analysis.get("weekly_patterns", {})
    if weekly.get("avg_discount_by_day"):
        days = weekly["avg_discount_by_day"]
        if days:
            best_day = max(days.items(), key=lambda x: x[1] if x[1] else 0)
            worst_day = min(days.items(), key=lambda x: x[1] if x[1] else 100)
            if best_day[1] and worst_day[1]:
                insights.append({
                    "title": "📅 Padrão Semanal Identificado",
                    "text": (
                        f"Os dados históricos indicam que {best_day[0]} é o dia "
                        f"com maiores descontos médios ({best_day[1]}%), enquanto "
                        f"{worst_day[0]} apresenta os menores descontos ({worst_day[1]}%). "
                        f"Esta informação pode ser utilizada para timing de campanhas "
                        f"e ajuste de preços competitivos."
                    ),
                })

    # Default insight if no data
    if not insights:
        insights.append({
            "title": "📝 Primeira Coleta de Dados",
            "text": (
                "Esta é a primeira coleta de dados. As análises comparativas "
                "e detecção de tendências serão disponibilizadas a partir da "
                "segunda coleta. Continue monitorando para construir o histórico "
                "necessário para insights acionáveis."
            ),
        })

    return insights


def render_report(analysis: dict) -> str:
    """Render the HTML email report from analysis data."""
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("email_report.html")

    price_changes = analysis.get("price_changes", [])
    increases = [c for c in price_changes if c["direction"] == "increase"]
    decreases = [c for c in price_changes if c["direction"] == "decrease"]

    # Calculate overall average discount
    categories = analysis.get("categories", {})
    discounts = [
        s["avg_discount_pct"]
        for s in categories.values()
        if s.get("avg_discount_pct") is not None
    ]
    avg_discount = round(sum(discounts) / len(discounts), 1) if discounts else 0

    promos = analysis.get("promotions", {})
    insights = generate_insights(analysis)

    html = template.render(
        report_date=datetime.now().strftime("%d/%m/%Y %H:%M"),
        total_products=analysis.get("total_products_tracked", 0),
        total_categories=len(categories),
        price_increases=len(increases),
        price_decreases=len(decreases),
        avg_discount=avg_discount,
        active_promos=promos.get("total_promo_products_today", 0),
        insights=insights,
        price_changes=price_changes,
        categories=categories,
        active_promotions=promos.get("active_promotions", []),
        weekly_patterns=analysis.get("weekly_patterns", {}),
        monthly_trends=analysis.get("monthly_trends", {}),
    )

    return html


def save_report(html: str) -> str:
    """Save the HTML report to disk."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    report_path = os.path.join(REPORTS_DIR, f"report_{today}.html")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"Report saved: {report_path}")
    return report_path


def send_email(html: str, subject: str = None):
    """Send the HTML report via email."""
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.warning(
            "Email credentials not configured. Set SMTP_USERNAME and SMTP_PASSWORD "
            "in .env file. Report saved to disk only."
        )
        return False

    if subject is None:
        today = datetime.now().strftime("%d/%m/%Y")
        subject = f"📊 Blinds.com Competitor Intelligence Report - {today}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USERNAME
    msg["To"] = RECIPIENT_EMAIL

    # Plain text fallback
    text_part = MIMEText(
        "Este relatório requer um cliente de email com suporte a HTML. "
        "Por favor, visualize em um navegador.",
        "plain",
        "utf-8",
    )
    html_part = MIMEText(html, "html", "utf-8")

    msg.attach(text_part)
    msg.attach(html_part)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_USERNAME, RECIPIENT_EMAIL, msg.as_string())
        logger.info(f"Email report sent successfully to {RECIPIENT_EMAIL}")
        return True
    except smtplib.SMTPException as e:
        logger.error(f"Failed to send email: {e}")
        return False
