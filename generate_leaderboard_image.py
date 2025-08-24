from PIL import Image, ImageDraw, ImageFont

def generate_leaderboard_image(top_players):
    base = Image.open("assets/SW.png").convert("RGBA")
    draw = ImageDraw.Draw(base)
    font = ImageFont.truetype("assets/font.ttf", 36)

    start_x, start_y = 100, 150
    spacing_y = 60

    for index, player in enumerate(top_players):
        name = player['username']
        kd = player['kd']
        draw.text((start_x, start_y + index * spacing_y), f"{index+1}. {name} - K/D: {kd}", font=font, fill=(255,255,255))

    base.save("kd_leaderboard.png")