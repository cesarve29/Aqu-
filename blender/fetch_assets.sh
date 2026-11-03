#!/bin/bash
# Descarga los datos CC0 de MakeHuman (malla base, esqueleto, pesos, piel, ojos, cejas).
# Solo se extraen archivos de datos; no se ejecuta codigo de terceros.
set -eu
cd "$(dirname "$0")"
[ -f assets_dl/mh/data/3dobjs/base.obj ] && exit 0
mkdir -p assets_dl && cd assets_dl
curl -sSL -o mpfb.zip "https://extensions.blender.org/download/sha256:c075b3e9b94b8e5556a5f03f4653602d02ea306de08126e8f55ed6dee28a2dad/add-on-mpfb-v2.0.18.zip"
curl -sSL -o system_assets.zip https://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip
mkdir -p mh
unzip -oq mpfb.zip "data/3dobjs/*" "data/rigs/standard/rig.default.json" "data/rigs/standard/weights.default.json" \
  "data/targets/macrodetails/universal-male-young-averagemuscle-averageweight.target.gz" \
  "data/targets/macrodetails/asian-male-young.target.gz" -d mh
unzip -oq system_assets.zip "skins/young_asian_male/*" "eyebrows/eyebrow001/*" "eyes/*" -d mh
rm -f mpfb.zip system_assets.zip
