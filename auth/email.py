import requests
from flask import current_app


def send_reset_email(to_email: str, reset_url: str) -> bool:
    api_key = current_app.config["BREVO_API_KEY"]
    payload = {
        "sender": {"name": "statimusic", "email": "contact@statimusic.fr"},
        "to": [{"email": to_email}],
        "subject": "Réinitialisation de ton mot de passe — statimusic",
        "htmlContent": f"""
        <div style="font-family: Inter, sans-serif; max-width: 480px; margin: auto; padding: 32px; background: #191919; color: #f2f2f2; border-radius: 12px;">
            <h2 style="color: #F2CC0D; margin-bottom: 24px;">statimusic</h2>
            <p>Tu as demandé à réinitialiser ton mot de passe.</p>
            <p>Clique sur le bouton ci-dessous — ce lien est valable <strong>1 heure</strong>.</p>
            <a href="{reset_url}" style="display:inline-block; margin: 24px 0; padding: 12px 24px; background: #F2CC0D; color: #191919; font-weight: 700; border-radius: 8px; text-decoration: none;">
                Réinitialiser mon mot de passe
            </a>
            <p style="font-size: 12px; color: #888;">Si tu n'as pas fait cette demande, ignore cet email. Ton mot de passe ne changera pas.</p>
        </div>
        """
    }
    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        json=payload,
        headers={"api-key": api_key, "Content-Type": "application/json"}
    )
    return response.status_code == 201
