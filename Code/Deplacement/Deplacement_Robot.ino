
#include <AFMotor.h>

// --- Déclaration des moteurs ---
AF_DCMotor moteur1(1);
AF_DCMotor moteur2(2);
AF_DCMotor moteur3(3);
AF_DCMotor moteur4(4);

// --- Vitesse et modes ---
float speed        = 200;    // vitesse manuelle
const float speedAuto = 180;   // vitesse en mode AUTO
const float turnSpeed    = 200;    // vitesse dédiée aux pivots
bool autoMode       = false;       // false = manuel, true = automatique

unsigned long lastSendTime = 0;
const unsigned long sendInterval = 500;  // 500 ms → 2 envois/s
  
// Compteur de fausses détections
int obstacleCount      = 0;
const int maxBadReads  = 3;  // nombre de lectures consécutives requises

// --- Pins capteurs ultrason ---
const int trigPinFront1 = 45;
const int echoPinFront1 = 44;
const int trigPinFront2 = 33;
const int echoPinFront2 = 32;
const int trigPinLeft   = 51;
const int echoPinLeft   = 50;

// --- Seuils (en cm) ---
const float seuilFront       = 50;   // détection obstacle frontal pour arrêt initial
const float seuilDetectMur   = 30;   // seuil de détection du mur à gauche
const float seuilFrontFollow = 30;   // seuil frontal pour finir le suivi
const float seuilTarget      = 20;   // distance idéale au mur
const float delta            = 15;   // tolérance zone morte

// Structure pour les mesures
struct Distances { float front; float left; };

// État du robot
volatile char dataChar = 0;
bool murDetecte = false;



// États du mode AUTO
enum AutoState { SEARCH_WALL, ROTATE_LOOK, FOLLOW_WALL };
AutoState autoState       = SEARCH_WALL;

// Pour la rotation 360°
const unsigned long rotateTimeout = 6000;  // durée estimée pour 360° (à calibrer)
unsigned long rotateStart        = 0;

// Gains et seuils pour le suivi de mur
const float Kp_follow    = 2.0;
const float maxCorr_follow = 100.0;
const float delta_follow = 10;     // zone morte




// --- Lecture asynchrone Bluetooth ---
void serialEvent1() {
  while (Serial1.available()) {
    char btData = Serial1.read();
    // On ignore CR/LF et tous les caractères qui ne sont pas dans la liste des commandes
    if (btData=='\n' || btData=='\r')        continue;
    if (btData!='F' && btData!='B' 
     && btData!='L' && btData!='R' 
     && btData!='S' && btData!='+' 
     && btData!='-' && btData!='A')         continue;

    dataChar = btData;
    Serial.print("BT reçu : "); Serial.println(dataChar);
    cmd();
  }
}


// --- Mesure distances ---
Distances measureDistances() {
  float front1, front2, gauche;

  // Front 1
  digitalWrite(trigPinFront1, LOW);  delayMicroseconds(2);
  digitalWrite(trigPinFront1, HIGH); delayMicroseconds(10);
  digitalWrite(trigPinFront1, LOW);
  front1 = pulseIn(echoPinFront1, HIGH) * 0.0343 / 2.0;

  // Front 2
  digitalWrite(trigPinFront2, LOW);  delayMicroseconds(2);
  digitalWrite(trigPinFront2, HIGH); delayMicroseconds(10);
  digitalWrite(trigPinFront2, LOW);
  front2 = pulseIn(echoPinFront2, HIGH) * 0.0343 / 2.0;

  // Gauche
  digitalWrite(trigPinLeft, LOW);  delayMicroseconds(2);
  digitalWrite(trigPinLeft, HIGH); delayMicroseconds(10);
  digitalWrite(trigPinLeft, LOW);
  gauche = pulseIn(echoPinLeft, HIGH) * 0.0343 / 2.0;

  Distances d;
  d.front = min(front1, front2);
  d.left  = gauche;

  return d;
}




void capteurUTS() {
  // 1) Lecture distances
  Distances m = measureDistances();

  // 2) Envoi limité des relevés (2 fois par seconde max)
  unsigned long now = millis();
  if (now - lastSendTime >= sendInterval) {
    lastSendTime = now;
    Serial.print("Dist Front: ");
    Serial.print(m.front);
    Serial.print(" cm  | Gauche: ");
    Serial.print(m.left);
    Serial.println(" cm");
  }

  // 3) Comptage des lectures « obstacle »
  if (dataChar == 'F') {
    if (m.front > 1 && m.front < seuilFront) {
      // lecture sous le seuil
      obstacleCount++;
    } else {
      // lecture hors de la zone dangereuse → on réinitialise
      obstacleCount = 0;
    }

    // 4) Si on a vu 3 lectures consécutives sous le seuil, on stoppe
    if (obstacleCount >= maxBadReads) {
      stop();
      Serial1.println(">> STOP (obstacle confirmé x3)");
      // on peut réinitialiser pour éviter de repasser ici immédiatement
      obstacleCount = 0;
    }
  }
}

// --- Mode automatique simplifié ---
void automaticMode() {
  Distances d = measureDistances();
  unsigned long now = millis();

  switch (autoState) {

    // 1) Recherche de mur devant → on avance à speedAuto
    case SEARCH_WALL:
      setVitesse(speedAuto);
      avancer();
      if (d.front > 1 && d.front < seuilFront) {
        autoState   = ROTATE_LOOK;
        rotateStart = now;
      }
      break;

    // 2) Pivote à gauche à turnSpeed pour chercher le mur à gauche
    case ROTATE_LOOK:
      setVitesse(turnSpeed);
      tournerDroite();
      if (d.left > 1 && d.left < seuilDetectMur) {
        autoState = FOLLOW_WALL;
      }
      else if (now - rotateStart > rotateTimeout) {
        autoState = SEARCH_WALL;
      }
      break;

    // 3) Suivi de mur à gauche
    
    case FOLLOW_WALL: {
      // 0) Si obstacle devant trop proche → on stoppe ou on recherche à nouveau
      if (d.front > 1 && d.front < seuilFrontFollow ) {
        stop();
        Serial1.println(">> STOP (obstacle frontal en mode FOLLOW_WALL)");
        autoState = SEARCH_WALL;  // ou : break; si tu veux juste t’arrêter
        break;
      }

      // 1) Plage pour le suivi
      const float lower = 15.0;   // borne inférieure
      const float upper = 45.0;  // borne supérieur

      // 2) Perte du mur → on repart en recherche
      if (d.left > 75) {
        autoState = SEARCH_WALL;
      }
      // 3) Trop loin du mur → pivot à droite jusqu'à revenir sous upper
      else if (d.left > upper) {
        setVitesse(turnSpeed);
        tournerGauche();
        delay(10);
      }
      // 4) Trop près du mur → pivot à gauche jusqu'à dépasser lower
      else if (d.left < lower) {
        setVitesse(turnSpeed);
        tournerDroite();
        delay(10);
      }
      // 5) Distance OK → on avance
      else {
        setVitesse(speedAuto);
        avancer();
      }
      break;
    }
  }
}




// --- Traitement commandes Bluetooth ---
void cmd() {
  switch (dataChar) {
    case 'F':
      setVitesse(speed);
      avancer();
      break;
    case 'B': setVitesse(speed); reculer(); break;
    case 'L': setVitesse(turnSpeed); tournerGauche(); break;
    case 'R': setVitesse(turnSpeed); tournerDroite(); break;
    case 'S':
      stop(); autoMode = false; murDetecte = false;
      Serial.println(">> AUTO OFF");
      break;
    case '+': speed = min(255.0, speed + 20); setVitesse(speed); break;
    case '-': speed = max(50.0, speed - 20); setVitesse(speed); break;
    case 'A': autoMode = true; Serial.println(">> AUTO ON"); break;
    default: break;
  }
}

// --- Setup & loop ---
void setup() {
  Serial.begin(230400);
  Serial1.begin(230400);
  pinMode(trigPinFront1, OUTPUT); pinMode(echoPinFront1, INPUT);
  pinMode(trigPinFront2, OUTPUT); pinMode(echoPinFront2, INPUT);
  pinMode(trigPinLeft, OUTPUT);    pinMode(echoPinLeft, INPUT);
  setVitesse(speed);
}

void loop() {
  unsigned long t0 = millis();
  if (autoMode) automaticMode();
  else capteurUTS();
  while (millis() - t0 < 10) { /* rien */ }
}

// --- Fonctions moteurs ---
void setVitesse(float spd) { moteur1.setSpeed(spd); moteur2.setSpeed(spd);
                              moteur3.setSpeed(spd); moteur4.setSpeed(spd); }
void avancer()  { moteur1.run(FORWARD); moteur2.run(FORWARD);
                  moteur3.run(FORWARD); moteur4.run(FORWARD); }
void reculer()  { moteur1.run(BACKWARD); moteur2.run(BACKWARD);
                  moteur3.run(BACKWARD); moteur4.run(BACKWARD); }
void tournerDroite() { moteur1.run(BACKWARD); moteur3.run(FORWARD);
                       moteur2.run(FORWARD);  moteur4.run(BACKWARD); }
void tournerGauche() { moteur1.run(FORWARD);  moteur3.run(BACKWARD);
                       moteur2.run(BACKWARD); moteur4.run(FORWARD); }
void stop()     { moteur1.run(RELEASE);    moteur2.run(RELEASE);
                  moteur3.run(RELEASE);    moteur4.run(RELEASE); }
