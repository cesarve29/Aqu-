#!/usr/bin/env python3
"""Genera audio/subtitulos.ass: titulo, narracion sincronizada con la voz real y cierre."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# texto en pantalla (con saltos \N); los tiempos salen de audio/tiempos_voz.txt (mix.py)
TEXT = [
    ('Narra', 'Hace cien años, el pueblo traicionó a su protector…\\Ny lo enterró sin cabeza bajo el viejo roble.'),
    ('Narra', 'Pero cada Halloween… el fuego recuerda.'),
    ('Narra', 'Y esta noche, el Jinete de la Calabaza Llameante\\Nvolvió a cabalgar.'),
    ('Narra', 'Todos huyeron. Todos… menos un niño.'),
    ('Narra', 'Porque en esos ojos de fuego no había odio…\\Nhabía tristeza.'),
    ('Narra', 'Buscaba la Llama Eterna.\\NLa única que podía devolverle el alma.'),
    ('Narra', 'Pero la llama dormía donde el fuego\\Nno quema rojo… sino azul.'),
    ('Narra', 'Y su guardián no perdonaba a ningún vivo.'),
    ('Rey', '¡NINGUNO SALDRÁ DE AQUÍ!'),
    ('Narra', 'Entonces el niño hizo lo que nadie\\Nse atrevió en cien años…'),
    ('Narra', 'El fuego azul se volvió dorado.\\NLa maldición… se hizo cenizas.'),
    ('Narra', 'Y si en Halloween ves una calabaza encendida bajo el viejo roble…\\Nno tengas miedo. Solo está descansando.'),
]


def ts(t):
    return f'{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}'


HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Narra,DejaVu Serif,46,&H00F0F4FF,&H000000FF,&H00140A05,&H96000000,0,1,0,0,100,100,1,0,1,3.2,1.5,2,140,140,70,1
Style: Titulo,DejaVu Serif,104,&H0040B4FF,&H000000FF,&H00001060,&H00000000,1,0,0,0,100,100,6,0,1,5,0,5,80,80,80,1
Style: Sub,DejaVu Serif,54,&H00C8E6FF,&H000000FF,&H00001040,&H00000000,0,1,0,0,100,100,10,0,1,3,0,5,80,80,80,1
Style: Rey,DejaVu Serif,66,&H00FFD08A,&H000000FF,&H00502000,&H96000000,1,0,0,0,100,100,4,0,1,4,2,2,80,80,90,1
Style: Final,DejaVu Serif,140,&H0030A0FF,&H000000FF,&H00003080,&H00000000,1,0,0,0,100,100,6,0,1,6,0,5,80,80,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def main():
    times = [tuple(map(float, l.split())) for l in open(os.path.join(HERE, 'audio', 'tiempos_voz.txt'))]
    ev = [
        (2.6, 8.6, 'Titulo', '{\\pos(960,470)\\fad(1100,900)\\blur3}EL JINETE DE LA\\NCALABAZA LLAMEANTE'),
        (4.2, 8.6, 'Sub', '{\\pos(960,690)\\fad(900,900)\\blur1}una leyenda de Halloween'),
    ]
    for (style, text), (a, b) in zip(TEXT, times):
        ev.append((a, b, style, text))
    ev.append((258.0, 260.0, 'Final', '{\\fad(500,200)\\blur2}¡Feliz Halloween!'))
    with open(os.path.join(HERE, 'audio', 'subtitulos.ass'), 'w', encoding='utf-8') as f:
        f.write(HEADER)
        for a, b, style, text in ev:
            fx = '' if text.startswith('{') else {'Rey': '{\\fad(120,400)}'}.get(style, '{\\fad(350,350)}')
            f.write(f'Dialogue: 0,{ts(a)},{ts(b)},{style},,0,0,0,,{fx}{text}\n')
    print('ok', len(ev), 'eventos')


if __name__ == '__main__':
    main()
