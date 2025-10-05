from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

def generate_leaderboard_image(top_players, week_label="WK0", background_path="assets/SW.png", output_path="kd_leaderboard.png"):
    # Load base leaderboard background
    base = Image.open(background_path).convert("RGBA")
    draw = ImageDraw.Draw(base)

    # Fonts
    main_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 45)
    footer_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 25)

    # Layout constants
    start_x_name = 285  # 165 + 120
    start_x_kd = 600    # 480 + 120
    start_y = 495       # 365 + 40 + 90
    spacing_y = 78      # base row spacing
    footer_y = 1295     # footer Y
    footer_x_date = 310 # 165 + 145
    footer_x_week = 595 # 480 + 145 - 30

    # Draw leaderboard rows
    for i, player in enumerate(top_players):
        name = player["username"]
        kd = player["kd"]
        y = start_y + i * spacing_y

        # Apply top/bottom row tweaks
        if i < 4:
            y += 10
        elif i >= 7:
            y += -10  # previously -15, now reduced

        draw.text((start_x_name, y), name, font=main_font, fill="black")
        draw.text((start_x_kd, y), f"{kd}", font=main_font, fill="black")

    # Footer
    date_str = datetime.now().strftime("%d/%m/%y")
    draw.text((footer_x_date, footer_y), date_str, font=footer_font, fill="black")
    draw.text((footer_x_week, footer_y), week_label, font=footer_font, fill="black")

    # Save result
    base.save(output_path)
    return output_path
