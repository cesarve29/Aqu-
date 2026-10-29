#!/usr/bin/env python3
"""Genera audio/subtitulos.ass: narracion en espanol, titulo inicial y cierre."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# (inicio, fin, estilo, texto)
LINES = [
    (0.4, 4.6, 'Titulo', 'LA MÁSCARA\\NDEL ECO AZUL'),
    (1.4, 9.6, 'Narra', 'Cada Halloween, el pueblo encendía cien calabazas…\\Npara que la oscuridad no se atreviera a entrar.'),
    (10.8, 16.2, 'Narra', 'Bailaban, cantaban… y olvidaban la vieja leyenda.'),
    (20.8, 25.0, 'Narra', 'Pero esa noche, algo salió de la niebla.'),
    (30.6, 37.3, 'Narra', 'No hacía ruido. No dejaba huellas.\\NSolo… apagaba la luz.'),
    (41.0, 45.3, 'Narra', 'Todos huyeron. Todos… menos una.'),
    (50.6, 58.2, 'Narra', 'Porque ella vio lo que nadie más vio:\\Naquella máscara intentaba gritar… y no podía.'),
    (60.6, 68.1, 'Narra', 'Hace siglos, una maldición le robó la voz…\\Ny la encerró donde ningún vivo se atreve a bajar.'),
    (70.8, 75.2, 'Narra', 'La niña lo siguió. Con miedo. Pero lo siguió.'),
    (80.8, 84.8, 'Narra', 'Hasta la bruja del pantano cerró sus cortinas.'),
    (90.8, 94.1, 'Narra', 'Y los muertos… le abrieron paso.'),
    (100.6, 106.6, 'Narra', 'La lápida más antigua guardaba el camino:\\Nla montaña del fuego azul.'),
    (110.8, 115.8, 'Narra', 'La Boca de Hueso.\\NQuien entra… no vuelve a salir.'),
    (120.8, 125.5, 'Narra', 'Ella se quedó en la entrada. Él siguió bajando.'),
    (130.8, 137.8, 'Narra', 'Allí abajo, el fuego no quema rojo.\\NQuema azul… porque arde con almas.'),
    (140.8, 145.4, 'Narra', 'Cientos de ojos vacíos se encendieron al mismo tiempo.'),
    (150.8, 155.0, 'Narra', 'Tensaron los arcos. Él no se detuvo.'),
    (160.8, 166.2, 'Narra', 'Un paso en falso…\\Ny el fuego azul lo devoraría para siempre.'),
    (170.6, 178.4, 'Narra', 'Y en el trono de huesos esperaba él:\\Nel Rey Esqueleto, guardián de la voz robada.'),
    (180.3, 182.3, 'Rey', '¡QUE NO SALGA VIVO!'),
    (203.4, 207.3, 'Narra', 'La máscara se quebró… pero no se rindió.'),
    (214.8, 218.5, 'Narra', 'Por fin… su voz volvió a casa.'),
    (230.8, 236.7, 'Narra', 'El fuego azul se volvió naranja.\\NLa maldición… se hizo cenizas.'),
    (240.6, 247.3, 'Narra', 'Esa noche, el pueblo entendió que no todo lo que da miedo…\\Nviene a hacer daño.'),
    (250.4, 258.9, 'Narra', 'Y cada Halloween, si una calabaza se apaga sin razón…\\Nno tengas miedo. Solo está de paso.'),
    (257.6, 260.0, 'Final', '¡Feliz Halloween!'),
]


def ts(t):
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f'{h}:{m:02d}:{s:05.2f}'


HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Narra,DejaVu Serif,46,&H00F0F4FF,&H000000FF,&H00140A05,&H96000000,0,1,0,0,100,100,1,0,1,3.2,1.5,2,140,140,70,1
Style: Titulo,DejaVu Serif,120,&H00FFE6B4,&H000000FF,&H00401C00,&H00000000,1,0,0,0,100,100,8,0,1,5,0,5,80,80,80,1
Style: Rey,DejaVu Serif,64,&H00FFD08A,&H000000FF,&H00502000,&H96000000,1,0,0,0,100,100,4,0,1,4,2,2,80,80,90,1
Style: Final,DejaVu Serif,130,&H0040A0FF,&H000000FF,&H00002060,&H00000000,1,0,0,0,100,100,6,0,1,5,0,5,80,80,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def main():
    os.makedirs(os.path.join(HERE, 'audio'), exist_ok=True)
    out = os.path.join(HERE, 'audio', 'subtitulos.ass')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(HEADER)
        for a, b, style, text in LINES:
            fx = {'Titulo': '{\\fad(900,900)\\blur2}', 'Final': '{\\fad(600,300)\\blur1.5}', 'Rey': '{\\fad(150,400)}'}.get(style, '{\\fad(400,400)}')
            f.write(f'Dialogue: 0,{ts(a)},{ts(b)},{style},,0,0,0,,{fx}{text}\n')
    print('ok', out)


if __name__ == '__main__':
    main()
