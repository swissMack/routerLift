/* **********************************************************************
    RouterLift V1.0.0

    V1: Startversion

    (c)2021 Frohnix Bastelbude -> https://www.youtube.com/user/Frohnix

    Die kommerzielle Nutzung der Software ist ausdrücklich untersagt.


************************************************************************* */

#include <Preferences.h>
#include <Arduino.h>
#include <ESP32Encoder.h>
#include <U8g2lib.h>
#include <SPI.h>
#include <Wire.h>
# define PULSEPIN 19
# define DIRPIN   15
# define HANDRADPIN_A_MINUS 27
# define HANDRADPIN_B_MINUS 14
# define PIN_BUTTON_SET_ZERO 13
# define PIN_BUTTON_SET_SPEED 4
# define PIN_BUTTON_MAX 16
# define PIN_BUTTON_AUTOZERO 17
# define PIN_BUTTON_AUTOZERO_ENABLED 5
# define PIN_BUTTON_TOOLCHANGE 32


ESP32Encoder handRad;

// *********************************** SPI Display ****************************************
U8G2_SSD1306_128X64_NONAME_F_4W_SW_SPI oledSPI(U8G2_R0, /* clock=*/ 18, /* data=*/ 23, /* cs=*/ 33, /* dc=*/ 25, /* reset=*/ 26);
// *********************************** I2C Display ****************************************
U8G2_SSD1306_128X64_NONAME_F_HW_I2C oledIIC(U8G2_R0, /* reset=*/ U8X8_PIN_NONE, /* clock=*/ 22, /* data=*/ 21);

// ********************************** Prog-Vars ****************************

float         threadPitch = 1.5; // Steigung der Spindel in mm
float         heightSensorMm = 9.0; // Sensor löst diesen Wert über dem 0-Punkt aus (negative Werte möglich)

int64_t         motorStepsPerRev = 400; // Steps Einstellung des Motors
int64_t         motorRamp = 25; // An/Abfahrrampe - kleiner = schneller (25=Standard)
int64_t         tcZeroRamp = 120; // Rampe für Toolchange und setZero
int64_t         tmpRamp = 0; // Ladervariable
bool            dirChange = true; // Drehrichtung des Motors umkehren (true / false)
int64_t         stepTimeMicros = 30; // Signallänge an die Endstufe in Mikrosekunden für einen Step
int64_t         motorSpeedMin = 10000; // Delay zwischen den Steps für minimale Drehzahl (größer= langsamer)
int64_t         motorSpeedMax = 250; // Delay zwischen den Steps für maximale Drehzahl (kleiner=schneller)
int64_t         motorSpeedTcZero =1000;
int64_t         motorSpeedTemp=0;

int             handWheelSlow  = 1;   // Multiplikator für feine Bewegung (Handrad-Klick = Motorsteps)
int             handWheelFast  = 5;  // Multiplikator für grobe Bewegung
int             handWheelSlowOld  = 0;   // Temp-Speicher für Setup und Neuberechnung des Encoders
int             handWheelFastOld  = 0;  // Temp-Speicher für Setup und Neuberechnung des Encoders
bool            handWheelIsFast = false;
bool            targetSet=false;
int64_t         targetSetValue=0;
int64_t         targetSetCounter=0;



// AB HIER KEINE VARIABLEN VERÄNDERN
// **************************** Microtimer ***************************
int64_t         microSec = 0; // Haupttimer
int64_t         microSecTmpDoStep = 0; // Delaytemp für Stepperschritte
//  ********************************* Steppermotor ******************************
volatile bool   doStep = false; // Motor soll einen Step machen
bool            doingStep = false; // Motor Step läuft;
bool            stepDir = true; // Drehrichtung
bool            stepDirIni = true; // Initiale drehrichtung, dient zur Kontrolle ob Drehrichtung während des laufs geändert wird
bool            runOut = false; // wird true sobald die Drehrichtung während des Laufs geändert wird
bool            runOutTargetSet = false;
int64_t         stepPos = 0; // aktuelle Motorposition in realen Motorsteps
int64_t         stepTarget = 0; // ziel Motorposition in realen Steps;
int64_t         stepTargetOld = 0; // vorherige Motorposition (Handrad, falss ein klick in die andere Richtung)float
float           motorSpeed = 0; // altueller MotorDelay ;
bool            motorRun = false; // Motor Läuft
int64_t         motorRunTimer = 30000; // nach x mikrosekunden wird motorRun auf false gesetzt
int64_t         motorRunTimerTmp = 0; // Tempspeicher
int64_t         way = 0; // absolute Wegstrecke des Motors
int64_t         accSteps = 0; // misst die Beschleunigungsschritte während der Strecke
int64_t         decSteps = 0; // misst die Bremsschritte während der Strecke
bool            acceleration = false; //motor beschleunigt
bool            deceleration = false; //motor bremst
bool            reachMotorOut = false;

// *********************************** Handrad **********************************
float         handRadMultiplier = 1;// 0.25; // HandradSteps -> MotorSteps & Einstellungssteps (Anzeige *4)
bool          handRadMode = true; // Position über Handrad
int64_t       handRadValue = 0; // hier wird die vorherige Position von Handrad geladen, bevor Settings
int           handWheelFactor = 0; // hier werden die Slow/Fast Variablen reingeladen

// *********************************** Sonstiges *********************************
float         mmPerStep = 0; // Rechenfaktor für die Anzeige
int64_t       stepPosDiff = 0; // Verschiebefaktor in Steps für Nullpunkt
float         mmDisplay = 0; // Anzeigewert fürs Display (unbearbeitet)
float         mmDisplayOld = 0; // Temp-Variable um Änderung festzustellen;
int64_t       setupCounter = 0; // Verzögerungscounter für Setup
bool          setupESP = false; // Setup-Mode
bool          ignoreZero = false; // Zero funktion ignorieren, wenn aus Setup zurück
int           setupMenu = 0;
int           lastSetupMenu = 0;

bool          buttonSetZero = true;
bool          buttonSetSpeed = true;
bool          buttonMaxHeight = true;
bool          buttonAutoZero = true;
bool          buttonToolChange = true;
bool          findZero = true; // Längensensor angeschlossen
bool          doFindZero = false; // prozedur zum höhe finden starten
int           findZeroSpeed = 20;
bool          doneFindZero = false; // prozedur höhe finden beendet
bool          driveToZero=false;
bool          doToolChange = false; // prozedur zum Werkzeugwechsel starten
int           toolChangeSpeed = 30;
int64_t       encoderSetupOld = 0; // vorherige Encoderposition im Setup um Richtung zu bestimmen
int64_t       workSpaceMm = 50; // Arbeitsbereich der Spindel
bool          workSpaceActive = false; // Workspace ist Aktiv
bool          workSpaceOnStartup = false; // Workspace bei Power on einstellen
bool          firstStart = true; // für autoworkspace nach PowerOn
bool          resetWorkSpace = false; // Workspace soll neu gesetzt werden (Toolchange)
int64_t       spindlePosMax = -1; // Position des Endschalters
int64_t       spindlePosMin = -1; // Posotion des Endschalters + WorkSpace
bool          typeEndstopNO = true;
bool          typeAutozeroNO = false;
bool          typeWlsNO = true;
bool          endstopError = false;
int64_t       endstopCounter = 0;
float         speedFactor=0;
bool          autoZeroRunning=false;

Preferences preferences;

TaskHandle_t Task1; // Dualcore

hw_timer_t * timer = NULL;
portMUX_TYPE timerMux = portMUX_INITIALIZER_UNLOCKED;

void IRAM_ATTR onTimer() {
  portENTER_CRITICAL_ISR(&timerMux);
  doingStep = false;
  portEXIT_CRITICAL_ISR(&timerMux);
}

void setup() {
  if (typeEndstopNO == false) {
    buttonMaxHeight = false;
  }
  if (typeAutozeroNO == true) {
    buttonAutoZero = false;
  }
  Serial.begin(115200);

  timer = timerBegin(0, 80, true);
  timerAttachInterrupt(timer, &onTimer, true);
  timerAlarmWrite(timer, 100000, true);
  timerAlarmEnable(timer);

  preferences.begin("routerLift", false);  //Ordner routerLift anlegen & verwenden
  motorSpeedMax     = preferences.getLong64("motorSpeedMax", motorSpeedMax);
  motorRamp         = preferences.getLong64("motorRamp", motorRamp);
  motorStepsPerRev  = preferences.getLong64("motorStepsPR", motorStepsPerRev);
  dirChange         = preferences.getBool("dirChange", dirChange);
  threadPitch       = preferences.getFloat("threadPitch", threadPitch);
  heightSensorMm    = preferences.getFloat("heightSensorMm", heightSensorMm);
  handWheelSlow     = preferences.getInt("handWheelSlow", handWheelSlow);
  handWheelFast     = preferences.getInt("handWheelFast", handWheelFast);
  toolChangeSpeed   = preferences.getInt("toolChangeSpeed", toolChangeSpeed);
  findZeroSpeed     = preferences.getInt("findZeroSpeed", findZeroSpeed);
  workSpaceMm       = preferences.getLong64("workSpaceMm", workSpaceMm);
  workSpaceOnStartup = preferences.getBool("workSpaceOnSt", workSpaceOnStartup);
  typeAutozeroNO    = preferences.getBool("typeAutozeroNO", typeAutozeroNO);
  typeEndstopNO     = preferences.getBool("typeEndstopNO", typeEndstopNO);
  typeWlsNO         = preferences.getBool("typeWlsNO", typeWlsNO);



  pinMode(PULSEPIN, OUTPUT);
  pinMode(DIRPIN, OUTPUT);
  digitalWrite(PULSEPIN, HIGH);

  pinMode(PIN_BUTTON_SET_ZERO, INPUT_PULLUP);
  pinMode(PIN_BUTTON_SET_SPEED, INPUT_PULLUP);
  pinMode(PIN_BUTTON_MAX, INPUT_PULLUP);
  pinMode(PIN_BUTTON_AUTOZERO, INPUT_PULLUP);
  pinMode(PIN_BUTTON_AUTOZERO_ENABLED, INPUT_PULLUP);
  pinMode(PIN_BUTTON_TOOLCHANGE, INPUT_PULLUP);

  ESP32Encoder::useInternalWeakPullResistors = UP;
  //handRad.attachFullQuad(HANDRADPIN_A_MINUS, HANDRADPIN_B_MINUS);
  handRad.attachSingleEdge(HANDRADPIN_A_MINUS, HANDRADPIN_B_MINUS);
  handRad.clearCount();
  handRadMode = true;
  handWheelFactor = handWheelFast;
  handWheelIsFast = true;
  //workSpaceOnStartup=true;
  xTaskCreatePinnedToCore(
    Task1code, /* Function to implement the task */
    "Task1", /* Name of the task */
    10000,  /* Stack size in words */
    NULL,  /* Task input parameter */
    2,  /* Priority of the task */
    &Task1,  /* Task handle. */
    0); /* Core where the task should run */


}


void loop() {
  speedFactor=motorStepsPerRev/800;
  tcZeroRamp=motorRamp*2;
  mmPerStep = threadPitch / motorStepsPerRev;
  buttonMaxHeight = digitalRead(PIN_BUTTON_MAX);
  buttonAutoZero = digitalRead(PIN_BUTTON_AUTOZERO);
  buttonToolChange = digitalRead(PIN_BUTTON_TOOLCHANGE);
  buttonSetSpeed     = digitalRead(PIN_BUTTON_SET_SPEED);
  
  if (!buttonSetSpeed && !setupESP) {
      delay(30);
      while (!digitalRead(PIN_BUTTON_SET_SPEED)) {
        delay(1);
        targetSetCounter++;        
        if(targetSetCounter>1000){
          if(targetSet==false){
            targetSet=true;
            targetSetValue=stepPos;
          }else{
            targetSet=false;
          }
          break;
        }
      }
      while (!digitalRead(PIN_BUTTON_SET_SPEED)) {}
      delay(30);
      if(targetSetCounter<=1000){
        if (handWheelFactor == handWheelFast) {
          handWheelFactor = handWheelSlow;
          handRad.setCount(stepPos / handWheelSlow / handRadMultiplier);
          handWheelIsFast = false;
        } else {
          handWheelFactor = handWheelFast;
          handRad.setCount(stepPos / handWheelFast / handRadMultiplier);
          handWheelIsFast = true;
        }
      }
      targetSetCounter=0;
      
    }
    
  if (digitalRead(PIN_BUTTON_AUTOZERO_ENABLED)) {
    if (typeAutozeroNO == false) {
      findZero = true;
    } else {
      findZero = false;
    }
  } else {
    if (typeAutozeroNO == false) {
      findZero = false;
    } else {
      findZero = true;
    }
  }
  microSec = esp_timer_get_time();


  // ****************************************** Handradbedienung *********************
  if (handRadMode == true) {
    handRad.resumeCount();
  }
  if (endstopError) {
    handRad.pauseCount();
  }
  if (setupESP == false && runOut == false && doToolChange==false) {
    stepTargetOld = stepTarget;
    if (handRad.getCount() < stepTargetOld - 1 || handRad.getCount() > stepTargetOld + 1) {
      stepTarget = handRad.getCount() * handRadMultiplier * handWheelFactor;
      if(!driveToZero){
      if (stepTarget > stepPos + motorStepsPerRev) {
        stepTarget = stepPos + motorStepsPerRev;
        handRad.setCount(stepTarget / handRadMultiplier / handWheelFactor);
      }
      if (stepTarget < stepPos - motorStepsPerRev) {
        stepTarget = stepPos - motorStepsPerRev;
        handRad.setCount(stepTarget / handRadMultiplier / handWheelFactor);
      }
      }else{
        if(stepPos==stepTarget){
          driveToZero=false;
        }
      }
    }
  }

  if (stepTarget > spindlePosMax && workSpaceActive == true) {
    stepTarget = spindlePosMax;    
    handRad.setCount(spindlePosMax / handRadMultiplier / handWheelFactor);
  }

  if (stepTarget < spindlePosMin && workSpaceActive == true) {
    stepTarget = spindlePosMin;    
    handRad.setCount(spindlePosMin / handRadMultiplier / handWheelFactor);
  }
  if(targetSet==true){
    if(stepTarget>targetSetValue){
      stepTarget=targetSetValue;
      handRad.setCount(targetSetValue / handRadMultiplier / handWheelFactor);
    }
  }

  //*********************************************************
  //            Soll/Ist Position für Motor
  //*********************************************************
  if (motorRun == false) {
    stepDirIni = stepDir;
  }
  if (motorRun == false) {
    tmpRamp = motorRamp;
  }
  if ((doToolChange || doFindZero || ((!buttonMaxHeight && typeEndstopNO) || (buttonMaxHeight && !typeEndstopNO))) && !endstopError && !setupESP) {
    tmpRamp = tcZeroRamp;
  }

if (stepTarget != stepPos) {
    if(motorRun==false){
      motorSpeedTemp=motorSpeedMax;
      if(doToolChange){
        motorSpeedTemp=motorSpeedTcZero;
      }
    }
    if (doingStep == false) {
      if (stepTarget < stepPos) {
        if (dirChange == false) {
          stepDir = false;
        } else {
          stepDir = true;
        }
        doStep = true;
        stepPos--;
      }
      if (stepTarget > stepPos) {
        if (dirChange == false) {
          stepDir = true;
        } else {
          stepDir = false;
        }
        doStep = true;
        stepPos++;
      }
      if (motorRun == false) {
        stepDirIni = stepDir;
      }
      motorRun = true;

      reachMotorOut = false;
      motorRunTimerTmp = esp_timer_get_time();



      way = abs(stepTarget - stepPos);
      acceleration = true;

      if (way <= accSteps) {
        acceleration = false;
        deceleration = true;
      }

      if (acceleration == true && motorSpeed > motorSpeedTemp) {
        motorSpeed = 1000000 * tmpRamp / motorStepsPerRev / ((accSteps ) + 1) ;
        accSteps++;
        decSteps++;
      }
      if (deceleration == true && motorSpeed < motorSpeedMin) {
        motorSpeed = 1000000 * tmpRamp / motorStepsPerRev / ((decSteps ) + 1) ;
        decSteps--;
        if (way > decSteps) {
          acceleration = true;
          deceleration = false;
          accSteps = decSteps;
        }
      }
      if (motorSpeed < motorSpeedTemp) {
        motorSpeed = motorSpeedTemp;
      }
      if (motorSpeed > motorSpeedMin) {
        motorSpeed = motorSpeedMin;
      }



    }
  } else {
    if (esp_timer_get_time() > motorRunTimerTmp + motorRunTimer) {
      motorRun = false;
      runOut = false;
    }
    motorSpeed = motorSpeedMin;
    accSteps = 0;
    decSteps = 0;
    acceleration = false;
    deceleration = false;
    if (runOutTargetSet == true) {
      runOut = false;
      runOutTargetSet = false;
    }
  }





  // *************** MAX HÖHE ************************+
  if (((!buttonMaxHeight && typeEndstopNO) || (buttonMaxHeight && !typeEndstopNO)) && !endstopError && !setupESP) {
    resetWorkSpace = true;
    doFindZero = false;
    doneFindZero = false;
    doToolChange = false;
    targetSet=false;
    handRad.pauseCount();
    if (stepTarget > stepPos) {
      stepTarget = stepPos;
    }

    if (stepTarget > stepPos - 20) {
      handRad.setCount(handRad.getCount() - (handWheelFast/handWheelFactor));
      endstopCounter = endstopCounter + (handWheelFactor * handRadMultiplier);
      if (endstopCounter > (motorStepsPerRev * 4 / threadPitch)) { //  ************************************************* FEHLER
        endstopCounter = 0;
        endstopError = true;
        resetWorkSpace = false;
      }
    }
  } else if (!endstopError) {
    if (!doToolChange) {
      handRad.resumeCount();
    }
    if (resetWorkSpace == true) {
      spindlePosMax = stepPos;
      spindlePosMin = spindlePosMax - ((workSpaceMm * motorStepsPerRev) / threadPitch);
      workSpaceActive = true;
      resetWorkSpace = false;
      endstopCounter = 0;
      handRadMode = true;
      /*
      preferences.putBool("workSpaceAct", workSpaceActive);
      preferences.putLong64("spindlePosMin", spindlePosMin);
      preferences.putLong64("spindlePosMax", spindlePosMax);
      */
    }
  }
  // ************** TOOLCHANGE ************************
  if (doToolChange && !setupESP) { 
    targetSet=false;   
    workSpaceActive = false;
    handRadMode = false;
    handRad.pauseCount();
    if (stepTarget < stepPos) {
      stepTarget = stepPos;
    }
    motorSpeedTemp=motorSpeedMax;
    stepTarget=stepPos+(toolChangeSpeed*2);
    handRad.setCount((stepTarget / handRadMultiplier / handWheelFactor)); 
    
  }
  // ************** AUTOZERO **************************
  if (doFindZero && !setupESP) {
    autoZeroRunning=true;
    targetSet=false;
    handRad.pauseCount();
    if (stepTarget < stepPos) {
      stepTarget = stepPos;
    }

    
      motorSpeedTemp=motorSpeedMax;
      stepTarget=stepPos+(findZeroSpeed*2);
      handRad.setCount((stepTarget / handRadMultiplier / handWheelFactor)); 
      if (stepPos >= spindlePosMax - 10 && workSpaceActive == true) {
        doFindZero = false;
        doneFindZero = false;
      }
    
  }
  if(autoZeroRunning){
  if (((!buttonAutoZero && typeWlsNO == true) || (buttonAutoZero && typeWlsNO == false)) && !setupESP && findZero == true) {
    if (doFindZero) {
      doFindZero = false;
      doneFindZero = true;
    }
    handRad.pauseCount();
    if (stepTarget > stepPos) {
      stepTarget = stepPos;
    }

    if (stepTarget > stepPos - 1 ) {
      handRad.setCount(handRad.getCount() - 1);
    }
  } else {
    if (doneFindZero && motorRun == false && !setupESP) {
      doneFindZero = false;      
      stepPosDiff = stepPos - (round(heightSensorMm * float(motorStepsPerRev) / threadPitch));
      driveToZero=true;
      stepTarget=stepPosDiff;
      handWheelFactor = handWheelSlow;      
      handWheelIsFast = false;      
      handRad.setCount((stepTarget / handRadMultiplier / handWheelFactor));      
      autoZeroRunning=false;
    }
    if (((buttonMaxHeight && typeEndstopNO) || (!buttonMaxHeight && !typeEndstopNO)) && !endstopError && !doToolChange) {
      handRad.resumeCount();
    }
  }
  }

  //*********************************************************
  //                      DOSTEP
  //*********************************************************  
  if (doStep == true && doingStep == false) {
    doingStep = true;
    digitalWrite(DIRPIN, stepDir);
    digitalWrite(PULSEPIN, LOW);
    delayMicroseconds(stepTimeMicros);
    digitalWrite(PULSEPIN, HIGH);
    microSecTmpDoStep = esp_timer_get_time();
    doStep = false;
    timerAlarmWrite(timer, motorSpeed, true);
  }
  /*
    if (doStep == false && doingStep == true) {
    if (esp_timer_get_time() >= microSecTmpDoStep + motorSpeed) {
      doingStep = false;
      ticker=esp_timer_get_time() - microSecTmpDoStep + motorSpeed;
    }
    }
  */
  //*********************************************************

}

void Task1code( void * parameter) {
  //oledIIC.begin();
  oledSPI.begin();
  oledIIC.begin();
  for (;;) {
    mmDisplay = mmPerStep * (stepPos - stepPosDiff);
    mmDisplay = round(mmDisplay * 100);
    mmDisplay = mmDisplay / 100;

    buttonSetZero     = digitalRead(PIN_BUTTON_SET_ZERO);    
    if ((!buttonToolChange || (workSpaceOnStartup && firstStart)) && !doFindZero  && !endstopError) {
      delay(30);
      while (!digitalRead(PIN_BUTTON_TOOLCHANGE)) {}
      delay(30);
      if (!setupESP) {
        if (!doToolChange && !setupESP ) {
          doToolChange = true;
          preferences.putBool("workSpaceAct", false);
        } else {
          doToolChange = false;
        }
      } else {
        setupMenu--;
        if (setupMenu < 1) {
          setupMenu = 15;
        }

      }
    }

//    if (!buttonSetSpeed && !setupESP) {
//      if (handWheelFactor == handWheelFast) {
//        handWheelFactor = handWheelSlow;
//        handRad.setCount(stepPos / handWheelSlow / handRadMultiplier);
//        handWheelIsFast = false;
//      } else {
//        handWheelFactor = handWheelFast;
//        handRad.setCount(stepPos / handWheelFast / handRadMultiplier);
//        handWheelIsFast = true;
//      }
//      delay(30);
//      while (!digitalRead(PIN_BUTTON_SET_SPEED)) {}
//      delay(30);
//    }
    if (!buttonSetZero && !doToolChange) {

      delay(30);
      while (!digitalRead(PIN_BUTTON_SET_ZERO)) {
        setupCounter++;
        delay(1);
        if (setupCounter > 2000) {
          setupCounter = 0;
          if (setupESP == false) {
            setupESP = true;
            handRadMode = false;
            handRadValue = handRad.getCount();
            handRad.setCount(0);
            encoderSetupOld = 0;
          } else {
            handRad.setCount(stepPos / handRadMultiplier / handWheelFactor);
            setupESP = false;
            ignoreZero = true;
            endstopError = false;
          }
          break;
        }
      }
      delay(30);
      if (setupESP == false && ignoreZero == false) {
        if (!findZero) {
          stepPosDiff = stepPos; 
          targetSet=false;         
        } else if (!endstopError) {
          if (!doFindZero) {
            doFindZero = true;
          } else {
            doFindZero = false;
          }
        }
      } else {
        if (setupMenu == 0) {
          oledIIC.clearBuffer();
          oledIIC.setFont(u8g2_font_helvB18_tf);
          oledIIC.setCursor(17, 25);
          oledIIC.print("SETUP");
          oledIIC.sendBuffer();
          oledSPI.clearBuffer();
          oledSPI.setFont(u8g2_font_helvB18_tf);
          oledSPI.setCursor(17, 25);
          oledSPI.print("SETUP");
          oledSPI.sendBuffer();
          handWheelSlowOld = handWheelSlow;
          handWheelFastOld = handWheelFast;
          handRadMode = false;

          handRad.resumeCount();
        } else if (ignoreZero == true) {
          oledIIC.clearBuffer();
          oledIIC.setFont(u8g2_font_helvB18_tf);
          oledIIC.setCursor(37, 25);
          oledIIC.print("END");
          oledIIC.sendBuffer();
          oledSPI.clearBuffer();
          oledSPI.setFont(u8g2_font_helvB18_tf);
          oledSPI.setCursor(37, 25);
          oledSPI.print("END");
          oledSPI.sendBuffer();
          handRad.setCount(stepPos / handRadMultiplier / handWheelFactor);
          handRadMode = true;
          if (motorStepsPerRev != preferences.getLong64("motorStepsPR", 0)) {
            workSpaceActive = false;
          }
          preferences.putLong64("motorSpeedMax", motorSpeedMax);
          preferences.putLong64("motorRamp", motorRamp);
          preferences.putLong64("motorStepsPR", motorStepsPerRev);
          preferences.putBool("dirChange", dirChange);
          preferences.putFloat("threadPitch", threadPitch);
          preferences.putFloat("heightSensorMm", heightSensorMm);
          preferences.putInt("handWheelSlow", handWheelSlow);
          preferences.putInt("handWheelFast", handWheelFast);
          preferences.putInt("toolChangeSpeed", toolChangeSpeed);
          preferences.putInt("findZeroSpeed", findZeroSpeed);
          preferences.putLong64("workSpaceMm", workSpaceMm);
          preferences.putBool("workSpaceOnSt", workSpaceOnStartup);
          preferences.putBool("typeAutozeroNO", typeAutozeroNO);
          preferences.putBool("typeEndstopNO", typeEndstopNO);
          preferences.putBool("typeWlsNO", typeWlsNO);
        }
        while (!digitalRead(PIN_BUTTON_SET_ZERO)) {}
        endstopError = false;
        setupMenu++;
        if (lastSetupMenu != 0) {
          setupMenu = lastSetupMenu - 1;
          if (lastSetupMenu == 1) {
            setupMenu = 15;
          }
          lastSetupMenu = 0;
        }
        if (setupMenu > 15) {
          setupMenu = 1;
        }
      }

    }
    setupCounter = 0;

    Serial.print("stepTarget:" + String((int32_t)stepTarget) + " ");
    Serial.print("stepPos:" + String((int32_t)stepPos) + " ");
    Serial.print("handRad.getCount:" + String((int32_t)handRad.getCount()) + " ");
    Serial.print("stepPosDiff:" + String((int32_t)stepPosDiff) + " ");
    Serial.print("motorSpeed:" + String((int32_t)motorSpeed) + " ");
    Serial.print("spindlePosMax:" + String((int32_t)spindlePosMax) + " ");
    Serial.print("spindlePosMin:" + String((int32_t)spindlePosMin) + " ");
    Serial.print("setupMenu:" + String((int32_t)setupMenu) + " ");
    Serial.print("lastSetupMenu:" + String((int32_t)lastSetupMenu) + " ");
    Serial.print("endstopCounter:" + String((int32_t)endstopCounter) + " ");
    Serial.print("endstopError:" + String((int32_t)endstopError) + " ");
    Serial.print("handRadMode:" + String((int32_t)handRadMode) + " ");
    Serial.print("stepDir:" + String((int32_t)stepDir) + " ");
    Serial.print("toolChangeSpeed:" + String((int32_t)toolChangeSpeed) + " ");
    Serial.print("motorRun:" + String((int32_t)motorRun * 500) + " ");
    Serial.print("HWS:" + String((int32_t)handWheelSlow) + " ");
    Serial.print("HWF:" + String((int32_t)handWheelFast) + " ");
    Serial.println("");


    oledIIC.clearBuffer();          // clear the internal memory
//    oledIIC.setFont(u8g2_font_helvB18_tf); // choose a suitable font
    oledSPI.clearBuffer();          // clear the internal memory
    oledSPI.setFont(u8g2_font_helvB18_tf); // choose a suitable font
    if (!setupESP) { // ********************* Normalbetrieb ********************
      if (mmDisplay >= 0) {
        if (mmDisplay < 10) {
//          oledIIC.setCursor(30, 25);
          oledSPI.setCursor(30, 25);
        } else {
//          oledIIC.setCursor(17, 25);
          oledSPI.setCursor(17, 25);
        }
      } else {
        if (mmDisplay > -10) {
//          oledIIC.setCursor(22, 25);
          oledSPI.setCursor(22, 25);
        } else {
//          oledIIC.setCursor(9, 25);
          oledSPI.setCursor(9, 25);
        }
      }
//      oledIIC.print(mmDisplay);
//      oledIIC.print(" mm");
      oledSPI.print(mmDisplay);
      oledSPI.print(" mm");

//      oledIIC.setFont(u8g2_font_helvB12_tf); // choose a suitable font
      oledSPI.setFont(u8g2_font_helvB12_tf); // choose a suitable font
      if (doFindZero || doneFindZero) {
//        oledIIC.setCursor(20, 50);
//        oledIIC.print("AUTOZERO");
        oledSPI.setCursor(20, 50);
        oledSPI.print("AUTOZERO");
      }
      if (doToolChange) {
//        oledIIC.setCursor(10, 50);
//        oledIIC.print("TOOLCHANGE");
        oledSPI.setCursor(10, 50);
        oledSPI.print("TOOLCHANGE");
      }
      if (!doFindZero && !doneFindZero && !doToolChange) { // *************************** targetSet
//        oledIIC.setCursor(45, 48);
        if(targetSet==false){          
          oledSPI.setCursor(45, 48);
        }else{          
          int ux=57;
          int uy=48;
          oledSPI.drawCircle(ux, uy-6, 7, U8G2_DRAW_ALL);
          oledSPI.drawCircle(ux, uy-6, 4, U8G2_DRAW_ALL);
          oledSPI.drawLine(ux-8, uy-6, ux+8, uy-6);
          oledSPI.drawLine(ux, uy-14, ux, uy+2);
          oledSPI.setCursor(69, 48);
          oledSPI.setFont(u8g2_font_helvB10_tf);
          float tsv=0;
          tsv = mmPerStep * (targetSetValue - stepPosDiff);
          tsv = round(tsv * 100);
          tsv = tsv / 100;
          oledSPI.print(tsv);
          oledSPI.print("mm");
          oledSPI.setFont(u8g2_font_helvB12_tf);
          oledSPI.setCursor(0,48);
                    
        }
        if (!endstopError) {
          if (handWheelIsFast == true) {
//            oledIIC.print("FAST");
            oledSPI.print("FAST");
          } else {
//            oledIIC.print("SLOW");
            oledSPI.print("SLOW");
          }
          if (findZero == true) {
//            oledIIC.drawDisc(125, 61, 2, U8G2_DRAW_ALL);
            oledSPI.drawDisc(125, 61, 2, U8G2_DRAW_ALL);
          }
        } else {
//          oledIIC.setCursor(0, 50);
//          oledIIC.print("ENDSTOP ERR");
          oledSPI.setCursor(0, 50);
          oledSPI.print("ENDSTOP ERR");
          handRad.pauseCount();

        }
        if (workSpaceActive) {
//          oledIIC.setCursor(5, 64);
//          oledIIC.setFont(u8g2_font_helvB08_tf);
//          oledIIC.print("WS");
          oledSPI.setCursor(5, 64);
          oledSPI.setFont(u8g2_font_helvB08_tf);
          oledSPI.print("WS");
          if (stepPos >= spindlePosMax - 10) {
//            oledIIC.print(" MAX");
            oledSPI.print(" MAX");
            doFindZero = false;
            doneFindZero = false;
          }
          if (stepPos <= spindlePosMin + 10) {
//            oledIIC.print(" MIN");
            oledSPI.print(" MIN");
          }
        }

      }
    } else { // *************************** SETUP **************************

      if (setupMenu == 1) {
//        oledIIC.setFont(u8g2_font_helvB12_tf);
//        oledIIC.setCursor(0, 15);
//        oledIIC.print("Motorspeed");
//        oledIIC.setFont(u8g2_font_helvB18_tf);
//        oledIIC.setCursor(0, 50);
//        oledIIC.print((int)(2060 - motorSpeedMax) / 20);
//        oledIIC.print(" %");
        oledSPI.setFont(u8g2_font_helvB12_tf);
        oledSPI.setCursor(0, 15);
        oledSPI.print("Motorspeed");
        oledSPI.setFont(u8g2_font_helvB18_tf);
        oledSPI.setCursor(0, 50);
        oledSPI.print((int)(2060 - motorSpeedMax) / 20);
        oledSPI.print(" %");
        motorSpeedMax = setVar(motorSpeedMax, 20, 60, 2060, true); // Variable,Step,min,max,reverse
      }
      if (setupMenu == 2) {
//        oledIIC.setFont(u8g2_font_helvB12_tf);
//        oledIIC.setCursor(0, 15);
//        oledIIC.print("Motor Acc");
//        oledIIC.setFont(u8g2_font_helvB18_tf);
//        oledIIC.setCursor(0, 50);
//        oledIIC.print((int)(105 - motorRamp));
//        oledIIC.print(" %");
        oledSPI.setFont(u8g2_font_helvB12_tf);
        oledSPI.setCursor(0, 15);
        oledSPI.print("Motor Acc");
        oledSPI.setFont(u8g2_font_helvB18_tf);
        oledSPI.setCursor(0, 50);
        oledSPI.print((int)(105 - motorRamp));
        oledSPI.print(" %");
        motorRamp = setVar(motorRamp, 1, 5, 105, true); // Variable,Step,min,max,reverse
      }
      if (setupMenu == 3) {
//        oledIIC.setFont(u8g2_font_helvB12_tf);
//        oledIIC.setCursor(0, 15);
//        oledIIC.print("Motor Steps");
//        oledIIC.setFont(u8g2_font_helvB18_tf);
//        oledIIC.setCursor(0, 50);
//        oledIIC.print((int)motorStepsPerRev);
        oledSPI.setFont(u8g2_font_helvB12_tf);
        oledSPI.setCursor(0, 15);
        oledSPI.print("Motor Steps");
        oledSPI.setFont(u8g2_font_helvB18_tf);
        oledSPI.setCursor(0, 50);
        oledSPI.print((int)motorStepsPerRev);
        motorStepsPerRev = setVar(motorStepsPerRev, 100, 200, 800, false); // Variable,Step,min,max,reverse
      }
      if (setupMenu == 4) {
//        oledIIC.setFont(u8g2_font_helvB12_tf);
//        oledIIC.setCursor(0, 15);
//        oledIIC.print("Motor Dir");
//        oledIIC.setFont(u8g2_font_helvB18_tf);
//        oledIIC.setCursor(0, 50);
        oledSPI.setFont(u8g2_font_helvB12_tf);
        oledSPI.setCursor(0, 15);
        oledSPI.print("Motor Dir");
        oledSPI.setFont(u8g2_font_helvB18_tf);
        oledSPI.setCursor(0, 50);
        if (dirChange == true) {
          oledIIC.print("CCW");
          oledSPI.print("CCW");
        } else {
          oledIIC.print("CW");
          oledSPI.print("CW");
        }
        dirChange = setVar(dirChange);
      }
      if (setupMenu == 5) {
//        oledIIC.setFont(u8g2_font_helvB12_tf);
//        oledIIC.setCursor(0, 15);
//        oledIIC.print("Thread Pitch");
//        oledIIC.setFont(u8g2_font_helvB18_tf);
//        oledIIC.setCursor(0, 50);
//        oledIIC.print((float)threadPitch);
//        oledIIC.print(" mm   ");
        oledSPI.setFont(u8g2_font_helvB12_tf);
        oledSPI.setCursor(0, 15);
        oledSPI.print("Thread Pitch");
        oledSPI.setFont(u8g2_font_helvB18_tf);
        oledSPI.setCursor(0, 50);
        oledSPI.print((float)threadPitch);
        oledSPI.print(" mm   ");
        threadPitch = float(setVar((long)(threadPitch * 10), 1, 5, 100, false)) / 10; // Variable,Step,min,max,reverse
      }
      if (setupMenu == 6) {
//        oledIIC.setFont(u8g2_font_helvB12_tf);
//        oledIIC.setCursor(0, 15);
//        oledIIC.print("Sensorheight");
//        oledIIC.setCursor(0, 50);
//        oledIIC.setFont(u8g2_font_helvB18_tf);
//        oledIIC.print((float)heightSensorMm);
//        oledIIC.print(" mm   ");
        oledSPI.setFont(u8g2_font_helvB12_tf);
        oledSPI.setCursor(0, 15);
        oledSPI.print("Sensorheight");
        oledSPI.setCursor(0, 50);
        oledSPI.setFont(u8g2_font_helvB18_tf);
        oledSPI.print((float)heightSensorMm);
        oledSPI.print(" mm   ");
        heightSensorMm = float(setVar((long)(heightSensorMm * 10), 1, 0, 200, false)) / 10; // Variable,Step,min,max,reverse
      }
      if (setupMenu == 7) {
        /*
        oledIIC.setFont(u8g2_font_helvB12_tf);
        oledIIC.setCursor(0, 15);
        oledIIC.print("Encoder Slow");
        oledIIC.setFont(u8g2_font_helvB18_tf);
        oledIIC.setCursor(0, 50);
        oledIIC.print((int)handWheelSlow);
        oledIIC.print(" Steps ");
        */
        oledSPI.setFont(u8g2_font_helvB12_tf);
        oledSPI.setCursor(0, 15);
        oledSPI.print("Encoder Slow");
        oledSPI.setFont(u8g2_font_helvB18_tf);
        oledSPI.setCursor(0, 40);
        oledSPI.print((int)handWheelSlow);
        oledSPI.print(" Steps ");
        oledSPI.setFont(u8g2_font_helvB10_tf);
        oledSPI.setCursor(35, 60);        
        oledSPI.print(float((threadPitch/motorStepsPerRev)*handWheelSlow*100));
        oledSPI.print("mm/U");
        handWheelSlow = setVar(handWheelSlow, 1, 1, 10, false); // Variable,Step,min,max,reverse
      }
      if (setupMenu == 8) {
        /*
        oledIIC.setFont(u8g2_font_helvB12_tf);
        oledIIC.setCursor(0, 15);
        oledIIC.print("Encoder Fast");
        oledIIC.setCursor(0, 50);
        oledIIC.setFont(u8g2_font_helvB18_tf);
        oledIIC.print((int)handWheelFast);
        oledIIC.print(" Steps ");
        */
        oledSPI.setFont(u8g2_font_helvB12_tf);
        oledSPI.setCursor(0, 15);
        oledSPI.print("Encoder Fast");
        oledSPI.setCursor(0, 40);
        oledSPI.setFont(u8g2_font_helvB18_tf);
        oledSPI.print((int)handWheelFast);
        oledSPI.print(" Steps ");
        oledSPI.setFont(u8g2_font_helvB10_tf);        
        oledSPI.setCursor(35, 60);        
        oledSPI.print(float((threadPitch/motorStepsPerRev)*handWheelFast*100));
        oledSPI.print("mm/U");
                
        handWheelFast = setVar(handWheelFast, 1, 1, 30, false); // Variable,Step,min,max,reverse
      }
      if (setupMenu == 9) {
//        oledIIC.setFont(u8g2_font_helvB12_tf);
//        oledIIC.setCursor(0, 15);
//        oledIIC.print("Toolchange Spd");
//        oledIIC.setCursor(0, 50);
//        oledIIC.setFont(u8g2_font_helvB18_tf);
//        oledIIC.print((int)toolChangeSpeed);
//        oledIIC.print(" %");
        oledSPI.setFont(u8g2_font_helvB12_tf);
        oledSPI.setCursor(0, 15);
        oledSPI.print("Toolchange Spd");
        oledSPI.setCursor(0, 50);
        oledSPI.setFont(u8g2_font_helvB18_tf);
        oledSPI.print((int)toolChangeSpeed);
        oledSPI.print(" %");
        toolChangeSpeed = setVar(toolChangeSpeed, 1, 1, 100, false); // Variable,Step,min,max,reverse
      }
      if (setupMenu == 10) {
//        oledIIC.setFont(u8g2_font_helvB12_tf);
//        oledIIC.setCursor(0, 15);
//        oledIIC.print("Autozero Spd");
//        oledIIC.setCursor(0, 50);
//        oledIIC.setFont(u8g2_font_helvB18_tf);
//        oledIIC.print((int)findZeroSpeed);
//        oledIIC.print(" %");
        oledSPI.setFont(u8g2_font_helvB12_tf);
        oledSPI.setCursor(0, 15);
        oledSPI.print("Autozero Spd");
        oledSPI.setCursor(0, 50);
        oledSPI.setFont(u8g2_font_helvB18_tf);
        oledSPI.print((int)findZeroSpeed);
        oledSPI.print(" %");
        findZeroSpeed = setVar(findZeroSpeed, 1, 1, 100, false); // Variable,Step,min,max,reverse
      }
      if (setupMenu == 11) {
//        oledIIC.setFont(u8g2_font_helvB12_tf);
//        oledIIC.setCursor(0, 15);
//        oledIIC.print("Workspace");
//        oledIIC.setCursor(0, 50);
//        oledIIC.setFont(u8g2_font_helvB18_tf);
//        oledIIC.print((int)workSpaceMm);
//        oledIIC.print(" mm");
        oledSPI.setFont(u8g2_font_helvB12_tf);
        oledSPI.setCursor(0, 15);
        oledSPI.print("Workspace");
        oledSPI.setCursor(0, 50);
        oledSPI.setFont(u8g2_font_helvB18_tf);
        oledSPI.print((int)workSpaceMm);
        oledSPI.print(" mm");
        workSpaceMm = setVar(workSpaceMm, 1, 1, 200, false); // Variable,Step,min,max,reverse
      }
      if (setupMenu == 12) {
//        oledIIC.setFont(u8g2_font_helvB12_tf);
//        oledIIC.setCursor(0, 15);
//        oledIIC.print("PwrOn Toolch.");
//        oledIIC.setCursor(0, 50);
//        oledIIC.setFont(u8g2_font_helvB18_tf);
        oledSPI.setFont(u8g2_font_helvB12_tf);
        oledSPI.setCursor(0, 15);
        oledSPI.print("PwrOn Toolch.");
        oledSPI.setCursor(0, 50);
        oledSPI.setFont(u8g2_font_helvB18_tf);
        if (workSpaceOnStartup == true) {
          oledIIC.print("OK");
          oledSPI.print("OK");
        } else {
          oledIIC.print("--");
          oledSPI.print("--");
        }
        workSpaceOnStartup = setVar(workSpaceOnStartup);
      }
      if (setupMenu == 13) {
//        oledIIC.setFont(u8g2_font_helvB12_tf);
//        oledIIC.setCursor(0, 15);
//        oledIIC.print("TLS ENA SW");
//        oledIIC.setCursor(0, 50);
//        oledIIC.setFont(u8g2_font_helvB18_tf);
        oledSPI.setFont(u8g2_font_helvB12_tf);
        oledSPI.setCursor(0, 15);
        oledSPI.print("TLS ENA SW");
        oledSPI.setCursor(0, 50);
        oledSPI.setFont(u8g2_font_helvB18_tf);
        if (typeAutozeroNO == true) {
          oledIIC.print("N O");
          oledSPI.print("N O");
        } else {
          oledIIC.print("N C");
          oledSPI.print("N C");
        }
        typeAutozeroNO = setVar(typeAutozeroNO);
      }

      if (setupMenu == 14) {
//        oledIIC.setFont(u8g2_font_helvB12_tf);
//        oledIIC.setCursor(0, 15);
//        oledIIC.print("TLS SW");
//        oledIIC.setCursor(0, 50);
//        oledIIC.setFont(u8g2_font_helvB18_tf);
        oledSPI.setFont(u8g2_font_helvB12_tf);
        oledSPI.setCursor(0, 15);
        oledSPI.print("TLS SW");
        oledSPI.setCursor(0, 50);
        oledSPI.setFont(u8g2_font_helvB18_tf);
        if (typeWlsNO == true) {
//          oledIIC.print("N O");
          oledSPI.print("N O");
        } else {
//          oledIIC.print("N C");
          oledSPI.print("N C");
        }
        typeWlsNO = setVar(typeWlsNO);
      }
      if (setupMenu == 15) {
//        oledIIC.setFont(u8g2_font_helvB12_tf);
//        oledIIC.setCursor(0, 15);
//        oledIIC.print("Endstop SW");
//        oledIIC.setCursor(0, 50);
//        oledIIC.setFont(u8g2_font_helvB18_tf);
        oledSPI.setFont(u8g2_font_helvB12_tf);
        oledSPI.setCursor(0, 15);
        oledSPI.print("Endstop SW");
        oledSPI.setCursor(0, 50);
        oledSPI.setFont(u8g2_font_helvB18_tf);
        if (typeEndstopNO == true) {
//          oledIIC.print("N O");
          oledSPI.print("N O");
        } else {
//          oledIIC.print("N C");
          oledSPI.print("N C");
        }
        typeEndstopNO = setVar(typeEndstopNO);
      }

    }
    oledIIC.sendBuffer();
    oledSPI.sendBuffer();

    if (ignoreZero == true) {
      while (!digitalRead(PIN_BUTTON_SET_ZERO)) {}
      lastSetupMenu = setupMenu;
      setupMenu = 0;
      ignoreZero = false;
      if (handWheelFast != handWheelFastOld || handWheelSlow != handWheelSlowOld) {
        if (handWheelIsFast == true) {
          handRad.setCount(stepPos / handWheelFast / handRadMultiplier);
          handWheelFactor = handWheelFast;
        } else {
          handRad.setCount(stepPos / handWheelSlow / handRadMultiplier);
          handWheelFactor = handWheelSlow;
        }
      } else {
        handRad.setCount(handRadValue);
      }
      handRadMode = true;
    }
    firstStart = false;
    delay(5);
  }
}

long setVar(long VAR, long STEP, long MIN, long MAX, bool REVERSE) {

  if (!REVERSE) {
    if (handRad.getCount() >= encoderSetupOld + 1) {
      VAR = VAR + STEP;
      encoderSetupOld = handRad.getCount();
    }
    if (handRad.getCount() <= encoderSetupOld - 1) {
      VAR = VAR - STEP;
      encoderSetupOld = handRad.getCount();
    }
  } else {
    if (handRad.getCount() >= encoderSetupOld + 1) {
      VAR = VAR - STEP;
      encoderSetupOld = handRad.getCount();
    }
    if (handRad.getCount() <= encoderSetupOld - 1) {
      VAR = VAR + STEP;
      encoderSetupOld = handRad.getCount();
    }
  }
  if (VAR > MAX) {
    VAR = MAX;
  }
  if (VAR < MIN) {
    VAR = MIN;
  }

  return VAR;
}

bool setVar(bool VAR) {
  if ((handRad.getCount() >= encoderSetupOld + 1) || (handRad.getCount() <= encoderSetupOld - 1)) {
    if (VAR == true) {
      VAR = false;
    } else {
      VAR = true;
    }
    encoderSetupOld = handRad.getCount();
  }
  return VAR;
}
