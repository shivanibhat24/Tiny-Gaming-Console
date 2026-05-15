/*
 * Xiao ESP32-C3 — Gaming Console Controller
 * 5 buttons: UP, DOWN, LEFT, RIGHT, OPTIONS
 *
 * Wiring (all buttons connect pin → GND):
 *   UP      → D0 (GPIO2)
 *   DOWN    → D1 (GPIO3)
 *   LEFT    → D2 (GPIO4)
 *   RIGHT   → D3 (GPIO5)
 *   OPTIONS → D4 (GPIO6)
 *
 * Protocol: Serial @ 115200 baud
 *   Each frame sent on change: "BXXXX\n"
 *   Where X is 0 (released) or 1 (pressed), order: U D L R O
 *   Example: "B10010\n" = UP pressed, RIGHT pressed
 *
 *   Full press events also send verb lines:
 *   "PRESSED:UP\n", "RELEASED:DOWN\n" etc.
 */

// ── Pin definitions ────────────────────────────────────────────────
#define PIN_UP      D0   // GPIO2
#define PIN_DOWN    D1   // GPIO3
#define PIN_LEFT    D2   // GPIO4
#define PIN_RIGHT   D3   // GPIO5
#define PIN_OPTIONS D4   // GPIO6

// ── Timing ─────────────────────────────────────────────────────────
#define DEBOUNCE_MS     20     // Debounce window
#define HEARTBEAT_MS  1000     // Send full state every N ms even if no change

// ── Button count ───────────────────────────────────────────────────
#define BTN_COUNT 5

// Button index constants
enum BtnIndex {
  BTN_UP = 0,
  BTN_DOWN,
  BTN_LEFT,
  BTN_RIGHT,
  BTN_OPTIONS
};

const char* BTN_NAMES[BTN_COUNT] = {
  "UP", "DOWN", "LEFT", "RIGHT", "OPTIONS"
};

const uint8_t BTN_PINS[BTN_COUNT] = {
  PIN_UP, PIN_DOWN, PIN_LEFT, PIN_RIGHT, PIN_OPTIONS
};

// ── State tracking ─────────────────────────────────────────────────
struct Button {
  uint8_t  pin;
  bool     state;          // Current debounced state (true = pressed)
  bool     rawState;       // Raw GPIO read
  uint32_t lastChangeMs;   // Last time raw state changed
};

Button buttons[BTN_COUNT];

uint32_t lastHeartbeatMs = 0;

// ── Setup ──────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);

  // Brief delay for USB CDC to enumerate on Xiao ESP32-C3
  delay(500);

  for (int i = 0; i < BTN_COUNT; i++) {
    buttons[i].pin           = BTN_PINS[i];
    buttons[i].state         = false;
    buttons[i].rawState      = false;
    buttons[i].lastChangeMs  = 0;

    pinMode(BTN_PINS[i], INPUT_PULLUP);
  }

  Serial.println("READY:XIAO_GAMEPAD_V1");
  sendFullState();
}

// ── Main loop ──────────────────────────────────────────────────────
void loop() {
  uint32_t now = millis();
  bool anyChange = false;

  for (int i = 0; i < BTN_COUNT; i++) {
    // Active LOW — pressed = GPIO LOW
    bool raw = (digitalRead(buttons[i].pin) == LOW);

    if (raw != buttons[i].rawState) {
      // Raw state changed; start/reset debounce timer
      buttons[i].rawState     = raw;
      buttons[i].lastChangeMs = now;
    }

    // Debounce: accept change only if stable for DEBOUNCE_MS
    if ((now - buttons[i].lastChangeMs) >= DEBOUNCE_MS) {
      if (raw != buttons[i].state) {
        buttons[i].state = raw;
        anyChange = true;

        // Send verb event for game logic convenience
        if (raw) {
          Serial.print("PRESSED:");
          Serial.println(BTN_NAMES[i]);
        } else {
          Serial.print("RELEASED:");
          Serial.println(BTN_NAMES[i]);
        }
      }
    }
  }

  // Send compact state frame on any change
  if (anyChange) {
    sendFullState();
  }

  // Periodic heartbeat so Python backend can detect disconnects
  if ((now - lastHeartbeatMs) >= HEARTBEAT_MS) {
    lastHeartbeatMs = now;
    sendFullState();
  }
}

// ── Helpers ────────────────────────────────────────────────────────

// Sends: "B<u><d><l><r><o>\n"  e.g. "B10010\n"
void sendFullState() {
  Serial.print("B");
  for (int i = 0; i < BTN_COUNT; i++) {
    Serial.print(buttons[i].state ? "1" : "0");
  }
  Serial.println();
}
