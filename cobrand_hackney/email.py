from noiseworks.sass import inline_image_html


def colours():
    color_green = "#00b341"
    color_black = "#000000"
    color_white = "#FFFFFF"
    color_hackney_pale_green = "#f2f7f0"
    color_hackney_dark_green = "#00664f"

    body_background_color = color_hackney_pale_green
    body_text_color = color_black
    header_background_color = color_black
    header_text_color = color_white
    secondary_column_background_color = color_white
    button_background_color = color_hackney_dark_green
    button_text_color = color_white

    logo_width = "200"  # pixel measurement, but without 'px' suffix
    logo_height = "36"  # pixel measurement, but without 'px' suffix
    logo_inline = inline_image_html("hackney/images/hackney-logo-white.png")
    header_padding = "20px 30px"

    return locals()


def settings(settings):
    only_column_style = "{only_column_style} border: 1px solid {column_divider_color}; border-top: none;".format(
        **settings
    )
    primary_column_style = "{primary_column_style} border: 1px solid {column_divider_color}; border-top: none;".format(
        **settings
    )
    secondary_column_style = "vertical-align: top; width: 50%; background-color: {secondary_column_background_color}; color: {secondary_column_text_color}; border: 1px solid {column_divider_color}; border-top: none; border-left: none;".format(
        **settings
    )
    return locals()
