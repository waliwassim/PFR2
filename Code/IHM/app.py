import os
import re
import unicodedata
import requests

from flask import Flask, request, jsonify, render_template, send_from_directory, Response, stream_with_context
from werkzeug.utils import secure_filename
import speech_recognition as sr

# --- CONFIGURATION DOSSIERS ---
UPLOAD_FOLDER     = "uploads"
TRANSCRIPT_FOLDER = "transcriptions"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TRANSCRIPT_FOLDER, exist_ok=True)

app = Flask(__name__, static_folder="static")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# === Constantes pour le filtre vocal ===
NOMBRES_FR = {
    "un":1, "deux":2, "trois":3, "quatre":4, "cinq":5,
    "six":6, "sept":7, "huit":8, "neuf":9, "dix":10,
    "onze":11, "douze":12, "treize":13, "quatorze":14,
    "quinze":15, "seize":16, "vingt":20, "trente":30,
    "quarante":40, "cinquante":50, "soixante":60,
    "cent":100, "mille":1000
}
ACTIONS    = {
    "avancer","avance","reculer","recule",
    "tourner","tourne",
    "localiser","localise","trouver","trouve",
    "stop","arreter",
    "ralentir","ralenti","accelerer","accelere",
    "suivre","suivi","va","vers"
}
DIRECTIONS = {"droite","gauche"}
COULEURS   = {"bleu","rose"}
OBJETS     = {"balle"}
SEPARATEURS= ["puis","et","ensuite","après","alors","plus tard"]

def nettoyer(texte):
    texte = texte.lower()
    texte = unicodedata.normalize("NFKD", texte).encode("ASCII","ignore").decode()
    texte = re.sub(r"[',.!?\-]", " ", texte)
    return re.sub(r"\s+", " ", texte).strip()

def mots_en_chiffre(mots):
    total = 0
    for mot in mots:
        if mot.isdigit():
            total += int(mot)
        elif mot in NOMBRES_FR:
            total += NOMBRES_FR[mot]
    return total

def extraire_actions(phrase):
    phrase = nettoyer(phrase)
    # mode automatique ?
    if "automatique" in phrase:
        return [("mode_automatique","","")]
    # découpe
    pattern = r"\b(?:" + "|".join(map(re.escape, SEPARATEURS)) + r")\b"
    frags = [f.strip() for f in re.split(pattern, phrase) if f.strip()]
    resultats = []
    for frag in frags:
        # suivi de balle ?
        if "balle" in frag and any(tok in frag for tok in ("localise","localiser","trouve","trouver","va","vers","suivre","suivi")):
            coul = next((c for c in COULEURS if c in frag), "bleu")
            resultats.append(("suivi_balle", coul, ""))
            continue
        tokens = frag.split()
        action=param1=param2=""
        temp=[]
        for i,mot in enumerate(tokens):
            if mot.isdigit():
                temp.append(mot); continue
            if mot in ACTIONS:
                action = mot
            elif mot in DIRECTIONS and action in {"tourner","tourne"}:
                param1 = mot
            elif mot in NOMBRES_FR:
                temp.append(mot)
            elif mot in {"m","metre","metres"} and temp:
                v = mots_en_chiffre(temp)
                param2 = str(int(v*100))
                temp=[]
            elif mot in {"cm","centimetres"} and temp:
                v = mots_en_chiffre(temp)
                param2 = str(int(v))
                temp=[]
            elif mot in {"mm","millimetres"} and temp:
                v = mots_en_chiffre(temp)
                param2 = str(int(v/10))
                temp=[]
            elif mot in {"degre","degres"} and temp:
                v = mots_en_chiffre(temp)
                param2 = str(int(v))
                temp=[]
        if action and not param2 and temp:
            param2 = str(int(mots_en_chiffre(temp)*100))
        if action:
            resultats.append((action,param1,param2))
    return resultats

def action_to_command(action,param1="",param2=""):
    a = action.lower()
    if a in {"avancer","avance"}:       return "F"
    if a in {"reculer","recule"}:       return "B"
    if a in {"tourner","tourne"}:       return "L" if param1=="gauche" else "R"
    if a in {"stop","arreter"}:         return "S"
    if a in {"accelerer","accelere"}:   return "+"
    if a in {"ralentir","ralenti"}:     return "-"
    if a == "mode_automatique":         return "A"
    # suivi_balle → pas de commande directe
    return ""

def calculer_delai(action,p2):
    try: v = int(p2)
    except: return 1.0
    a = action.lower()
    if a in {"avancer","avance","reculer","recule"}:
        return round((v/100)*1.15,2)
    if a in {"tourner","tourne"}:
        return round((v/90)*1.35,2)
    return 1.0

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_audio():
    if "audio" not in request.files:
        return jsonify(error="Aucun fichier reçu"), 400
    f = request.files["audio"]
    filename = secure_filename(f.filename)
    wav_path = os.path.join(UPLOAD_FOLDER, filename)
    f.save(wav_path)

    try:
        r = sr.Recognizer()
        with sr.AudioFile(wav_path) as src:
            audio_data = r.record(src)
        texte = r.recognize_google(audio_data, language="fr-FR")
    except:
        return jsonify(error="Transcription échouée", commands=["S"], delays=[1.0])

    # Sauvegarde de la transcription
    base = os.path.splitext(filename)[0]
    with open(os.path.join(TRANSCRIPT_FOLDER, base + ".txt"), "w", encoding="utf-8") as tf:
        tf.write(texte)

    actions = extraire_actions(texte)
    commands = []
    delays = []
    types    = []
    colors   = []
    for action, p1, p2 in actions:
        cmd = action_to_command(action, p1, p2)
        commands.append(cmd)
        delays.append(calculer_delai(action, p2))
        # taguer type et couleur pour le suivi
        if action in {"localiser","localise","trouver","trouve"}:
            types.append("suivi_balle")
            # extraire la couleur si mentionnée
            if "bleu" in p2:
                colors.append("bleu")
            elif "rose" in p2 or "rose" in p2:
                colors.append("rose")
            else:
                colors.append("bleu")
        else:
            types.append(action)
            colors.append("")
    if not commands:
        commands = ["S"]
        delays   = [1.0]
        types    = ["stop"]
        colors   = [""]

    return jsonify(
        transcription=texte,
        commands=commands,
        delays=delays,
        types=types,
        colors=colors
    )

@app.route("/transcriptions/<path:filename>")
def get_transcript(filename):
    return send_from_directory(TRANSCRIPT_FOLDER, filename, as_attachment=True)

# === Proxy vers la Raspberry Pi ===
PI_BASE = "http://172.20.10.2:8000"

@app.route("/pi/coords")
def proxy_coords():
    r = requests.get(f"{PI_BASE}/coords", timeout=2)
    return jsonify(r.json()), r.status_code

@app.route("/pi/video_feed")
def proxy_video_feed():
    remote = requests.get(f"{PI_BASE}/video_feed", stream=True)
    return Response(
        stream_with_context(remote.iter_content(chunk_size=1024)),
        content_type=remote.headers.get("Content-Type")
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
