from email.mime.image import MIMEImage
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from notifications_python_client.notifications import NotificationsAPIClient
from noiseworks import cobrand


def send_sms(to, text):
    notifications_client = NotificationsAPIClient(settings.NOTIFY_API_KEY)
    notifications_client.send_sms_notification(
        phone_number=to,
        template_id=settings.NOTIFY_TEMPLATE_ID,
        personalisation={"text": text},
    )


def send_email(to, subject, template, data):
    body_text = render_to_string(f"{template}.txt", data)
    settings = email_colours()
    settings.update(cobrand.email.override_colours())
    email_settings(settings)
    settings.update(cobrand.email.override_settings(settings))
    data.update(settings)
    body_html = render_to_string(f"{template}.html", data)

    logo = MIMEImage(data["logo_inline"]["data"])
    logo.add_header("Content-ID", f"<{data['logo_inline']['id']}>")

    message = EmailMultiAlternatives(subject, body_text, None, [to])
    message.mixed_subtype = "related"
    message.attach_alternative(body_html, "text/html")
    message.attach(logo)
    message.send()


def email_colours():
    color_blue = "#0F87C5"
    color_blue_darker = "#00527C"
    color_blue_pale = "#D6E2EB"
    color_grey = "#D2D2D2"
    color_gunmetal = "#42494C"
    color_gunmetal_light = "#81959D"
    color_yellow = "#FDD008"
    color_red_dark = "#ce2626"
    color_green_dark = "#39a515"
    color_black = "#000000"
    color_white = "#ffffff"

    link_text_color = color_blue
    link_hover_text_color = color_blue_darker

    body_background_color = color_gunmetal
    body_font_family = "Helvetica, Arial, sans-serif"
    body_text_color = color_gunmetal_light

    header_background_color = color_yellow
    header_text_color = color_black
    header_padding = (
        "15px 20px"  # a full CSS padding property (eg: top/right/bottom/left)
    )

    logo_file = "email-logo.gif"
    logo_width = "192"  # pixel measurement, but without 'px' suffix
    logo_height = "35"  # pixel measurement, but without 'px' suffix
    logo_font_size = "24px"

    primary_column_background_color = color_white
    primary_column_text_color = color_black
    secondary_column_background_color = color_blue_pale
    secondary_column_text_color = color_gunmetal
    column_divider_color = color_grey
    column_padding = 20  # a single CSS pixel measurement without the "px" suffix

    button_border_radius = "4px"  # a full CSS border-radius property
    button_background_color = color_yellow
    button_text_color = color_black
    button_font_weight = "bold"

    return locals()


def email_settings(colours):
    # Variables used inside the email templates.

    table_reset = 'cellspacing="0" cellpadding="0" border="0" width="100%"'
    wrapper_table = table_reset

    link_style = "color: {link_text_color};".format(**colours)
    link_hover_style = "text-decoration: none; color: {link_hover_text_color};".format(
        **colours
    )

    td_style = "font-family: {body_font_family}; font-size: 16px; line-height: 21px; font-weight: normal; text-align: left;".format(
        **colours
    )

    body_style = "margin: 0;"
    wrapper_style = "{td_style} background: {body_background_color}; color: {body_text_color};".format(
        **colours, **locals()
    )

    wrapper_max_width = 620  # in pixels without "px" suffix
    wrapper_min_width = 520  # in pixels without "px" suffix

    hint_min_width = wrapper_min_width - (colours["column_padding"] * 2)
    hint_style = "min-width: {hint_min_width}px; padding: {column_padding}px; color: {body_text_color}; font-size: 12px; line-height: 18px;".format(
        **colours, **locals()
    )

    warning_style = "min-width: {hint_min_width}x; padding: {column_padding}px; background-color: {color_red_dark}; color: {color_white};".format(
        **colours, **locals()
    )

    header_style = "padding: {header_padding}; background: {header_background_color}; color: {header_text_color};".format(
        **colours, **locals()
    )

    only_column_style = "padding: {column_padding}px; vertical-align: top; background-color: {primary_column_background_color}; color: {primary_column_text_color};".format(
        **colours, **locals()
    )
    primary_column_style = "vertical-align: top; width: 50%; background-color: {primary_column_background_color}; color: {primary_column_text_color};".format(
        **colours, **locals()
    )
    secondary_column_style = "vertical-align: top; width: 50%; background-color: {secondary_column_background_color}; color: {secondary_column_text_color}; border-left: 1px solid {column_divider_color};".format(
        **colours, **locals()
    )

    # Use these to add padding inside primary and secondary columns.
    start_padded_box = '<table cellspacing="0" cellpadding="{column_padding}" border="0" width="100%"><tr><th style="{td_style}">'.format(
        **colours, **locals()
    )
    end_padded_box = "</th></tr></table>"

    logo_style = "font-size: {logo_font_size}; line-height: {logo_height}px; vertical-align: middle;".format(
        **colours, **locals()
    )
    h1_style = "margin: 0 0 20px 0; font-size: 28px; line-height: 30px;"
    h2_style = "margin: 0 0 20px 0; font-size: 21px; line-height: 24px;"
    p_style = "margin: 0 0 0.8em 0;"
    secondary_p_style = "font-size: 14px; line-height: 20px; {p_style}".format(
        **colours, **locals()
    )

    # The below is so the buttons work okay in Outlook: https://litmus.com/blog/a-guide-to-bulletproof-buttons-in-email-design
    button_style = "display: inline-block; border: 10px solid {button_background_color}; border-width: 10px 15px; border-radius: {button_border_radius}; background-color: {button_background_color}; color: {button_text_color}; font-size: 18px; line-height: 21px; font-weight: {button_font_weight}; text-decoration: underline;".format(
        **colours, **locals()
    )

    colours.update(locals())
