// ===========================================================================
// OPS SENSOR UNIT — ESP32 environmental monitor
// mode: 0 assembly | 1 base only | 2 cover only | 3 exploded
// ===========================================================================
mode = 0;
EXPLODE = 34;   // exploded-view gap, animatable
$fn = 40;

// ---- real component data --------------------------------------------------
BB      = [50.14, 38.54, 6.50];   // mini breadboard (bread.stl, measured)
ESP     = [63.0, 25.5, 13.0];     // ESP32-S3 DevKitC seated on the breadboard
// 1.3" SH1106 module. These are the MANUFACTURER'S DRAWING figures carried
// over from the author's shopkeeper project, where two caliper readings were
// proved wrong on the bench: the holes are 3.00 (M3) and the 4.0-4.5 reading
// was the copper annulus around them, and the board is 35.40 wide not 35.0.
OLED_PCB   = [35.40, 33.50, 1.20];
OLED_PANEL = [34.50, 23.00];      // glass, standing 1.4-1.5 proud of the PCB
OLED_GLASS = [34.8, 25.8];        // the cutout: clears the glass on both axes
OLED_HOLES = [30.40, 28.50];      // 2.50 inset all round: 35.40-5.00, 33.50-5.00
OLED_HOLE_D = 3.30;               // M3 clearance. NOT M2 - this cost a print once
// The display screws to four printed pillars hanging from the inside of the
// deck, rather than resting on a ledge. Printed deck-down the pillars point
// UP, so they cost nothing and need no support.
// The pillars are PEGS that enter the module's own 3.00 holes, not bosses
// sitting beside them: 2.90 across, which is a press fit in a printed 3.00
// hole and still assembles by hand. They locate the board in both axes and
// stop it rotating; the clamp holds it against them.
OLED_PIL_D  = 3.00;               // pushed to 3.00 - the module's hole size
OLED_PIL_H  = 4.2;                // through the 1.20 board, standing proud
// The active area is 29.42 x 14.70 and is NOT centred: it sits 2.05mm toward
// the header edge, because the driver IC and FPC bond eat the bottom 6.20mm of
// the glass. The cutout is 25.8 tall against a 14.70 active area, so the offset
// is absorbed - but a tight symmetric window would clip the status line.
MQ_CAN_D   = 20.0;                // MQ-135 steel can (protrudes, "half exposed")
MQ_PCB     = [32.0, 22.0, 2.0];
DHT_BODY   = [15.5, 12.0, 5.5];   // DHT11 blue body (protrudes)
DHT_PCB    = [23.0, 12.0, 2.0];

// ---- shell -----------------------------------------------------------------
WALL   = 2.6;
GAP    = 0.8;                     // wiring slack around the breadboard
FLOOR  = 2.6;
CORNER = 7.0;                     // corner radius, drives the rugged look
BOSS_IN = 1.8;                    // boss inset: keeps the screw well out of the cavity
BOSS_R = 4.6;                     // corner boss: sized for M3, not oversized
PLATE_T = 3.0;                    // bottom cover thickness
PLATE_CLR = 0.25;                 // slip fit of the plate into the body

// interior sized from the stack, not guessed
// ---- solved from the tolerance audit, not guessed ------------------------
IN  = [max(BB[0], ESP[0]) + 2*GAP + 8,      // 72.6  devkit + 4.8/side
       BB[1] + 2*GAP + 14,                  // 54.1  incl. 12.8mm front sensor bay
       BB[2] + ESP[2] + 9];                 // 28.5  display clears the devkit by 6.6
OUT = [IN[0] + 2*WALL, IN[1] + 2*WALL, IN[2] + FLOOR + WALL + 2];
SENS_AX = FLOOR + 11.9;                     // 14.5 sensor axis: port clears floor by 1.5
SPLIT   = SENS_AX + 11.6;                   // 26.1 MQ port sits wholly inside the base wall
BB_Y    = 5.0;                              // breadboard centre, 2.8mm rear gap

echo(str("OLED underside ", OUT[2]-WALL-4.4, "  vs devkit top ", FLOOR+BB[2]+ESP[2], " mm"));
echo(str("OUTER  ", OUT[0], " x ", OUT[1], " x ", OUT[2], " mm"));

// rounded slab: hull of 4 vertical cylinders
module rslab(sz, r, ch=0){
  hull() for(sx=[-1,1], sy=[-1,1])
    translate([sx*(sz[0]/2-r), sy*(sz[1]/2-r), 0])
      cylinder(h=sz[2], r=r);
}
// same but with a chamfered top edge (tapers in by `ch`)
module rslab_ch(sz, r, ch=1.6){
  hull(){
    rslab([sz[0], sz[1], sz[2]-ch], r);
    translate([0,0,sz[2]-ch]) rslab([sz[0]-2*ch, sz[1]-2*ch, ch], max(r-ch,0.6));
  }
}
// Screw corners are triangular webs spanning the two walls, not towers off the
// floor. Top face is full size, underside tapers 45 deg so it self-supports.
WEB_L = 13.0;    // leg length at the top
WEB_H = 9.0;     // height of the web (bottom legs = WEB_L - WEB_H -> 45 deg)
module corner_web(sx, sy, top){
  cx = sx*(OUT[0]/2-WALL); cy = sy*(OUT[1]/2-WALL);
  translate([cx, cy, top-WEB_H])
    hull(){
      translate([0,0,WEB_H-0.01])
        linear_extrude(0.01) polygon([[0,0], [-sx*WEB_L,0], [0,-sy*WEB_L]]);
      linear_extrude(0.01)
        polygon([[0,0], [-sx*(WEB_L-WEB_H),0], [0,-sy*(WEB_L-WEB_H)]]);
    }
}
module corner_bosses(h, r=BOSS_R, inset=BOSS_IN){
  for(sx=[-1,1], sy=[-1,1]) corner_web(sx, sy, h);
}
// M3 x 5 screws: only 2.0mm of cover under the head, so 3.0mm bites the post
module corner_screws(z0, deep=true){
  for(sx=[-1,1], sy=[-1,1])
    translate([sx*(OUT[0]/2-BOSS_R-BOSS_IN), sy*(OUT[1]/2-BOSS_R-BOSS_IN), 0]){
      translate([0,0,z0]) cylinder(h=40, d=3.2);                        // M3 shank, close clearance
      if(deep){
        translate([0,0,OUT[2]-7.6]) cylinder(h=9, d=5.9);               // head well: M3 cap is 5.5, pan 5.6
        translate([0,0,OUT[2]-8.5]) cylinder(h=1.0, d1=3.2, d2=5.9);
      }
    }
}
// Corner pads, cut INTO the deck rather than standing proud of it. Raised pads
// would be the only thing touching the plate when the cover prints face-down,
// which is the orientation that needs no support.
module corner_pads(){ }
module corner_pad_cuts(){
  for(sx=[-1,1], sy=[-1,1])
    translate([sx*(OUT[0]/2-BOSS_R-BOSS_IN), sy*(OUT[1]/2-BOSS_R-BOSS_IN), OUT[2]-0.8])
      difference(){ cylinder(h=2, r=BOSS_R-0.6); translate([0,0,-0.1]) cylinder(h=3, r=BOSS_R-2.1); }
}
// slots in a side wall: stacked in Z, running along Y, cutting through X
module louvres(n=5, len=17, w=2.2, pitch=4.4){
  for(i=[0:n-1]) translate([0, 0, (i-(n-1)/2)*pitch])
    hull() for(sy=[-1,1]) translate([0, sy*(len/2-w/2), 0])
      rotate([0,90,0]) cylinder(h=30, d=w, center=true);
}
// slots in the top skin: spaced in X, running along Y, cutting through Z
module top_slots(n=4, len=16, w=2.2, pitch=4.6){
  for(i=[0:n-1]) translate([(i-(n-1)/2)*pitch, 0, 0])
    hull() for(sy=[-1,1]) translate([0, sy*(len/2-w/2), 0]) cylinder(h=20, d=w, center=true);
}

// ---- cutouts ---------------------------------------------------------------
// front face is -Y. sensors sit "half exposed" through it.
MQ_X  =  8.0;     // front wall, clears both corner posts
// DHT11 now lives in the TOP COVER beside the screen. It does not fit across
// the strip left of the display pocket (23mm module, 18.2mm strip), so it is
// mounted turned 90 deg: its long axis runs front-to-back.
DHT_TOP_X = -27.0;
DHT_TOP_Y = -2.0;
// The module has ONE mounting hole, measured Ø3.70. A post hangs from the
// pocket ceiling and passes through it: the board drops over the post, which
// locates it and stops it rotating, then an M3 screw goes UP into the post
// from underneath and its head clamps the board against the deck.
// The 3-pin breakout, read off the photo: blue body at one end, then the
// mounting hole with the red power LED beside it, then the VCC/DAT/GND header.
// 12.8 x 16.1 is the BLUE BODY - the carrier board is about twice as long, so
// the board is wider than the body on every side and bottom-loading gives a
// proper ledge to clamp against.
DHT_BODY2   = [13.2, 16.4];   // measured blue body
DHT_WIN     = [13.8, 17.0];   // window it pokes through, 0.3/side
DHT_CARRIER = [15.0, 34.0];   // pocket for the board - deliberately generous,
                              // the window and the screw do the locating
DHT_HOLE_D  = 3.70;           // module's own mounting hole
// The module mounts ON TOP of the deck: it sits on a raised boss, screwed down
// through its own hole, with the blue body in free air where it belongs. The
// deck only has to pass the wires and show the LED.
DHT_BOSS_D  = 3.4;            // the tower - the only DHT mount feature there is
DHT_BOSS_H  = 2.5;            // how far it stands proud of the deck
DHT_BOSS_HOLE = 3.5;          // module hole measures 3.5 - M3 passes with 0.25/side
DHT_WIRE    = [9.0, 5.0];     // wire slot through the deck
DHT_BODY_Y  = -8.0;           // body centre; its far edge lands at y = +0.05
// The LED and the screw hole are placed from the PHOTO, not from calipers, so
// both are SLOTTED along the board's length. A slot absorbs a couple of mm of
// error in either direction: the LED still shows, and an M3 self-tapper still
// finds meat wherever the board's hole actually sits.
// "DHT11 to LED open 22.7mm" can read as 22.7 from the body's CENTRE (LED at
// +14.7 here) or from its outer EDGE (LED at +6.5). The slot is lengthened to
// span both rather than betting on one reading.
DHT_OPEN_L  = 22.7;           // MEASURED: body end -> LED, one opening
DHT_LED_W   = 4.5;            // extension width - narrowed so it clears the
                              // centre screw hole with real material between them
DHT_LED_X   = 5.5;            // LED sits just off the centreline, beside the screw
DHT_HOLE_X  =  0.0;           // screw is on the board's CENTRELINE, right by the LED
DHT_HOLE_Y  = 3.8;            // board CENTRE: immediately past the body window,
                              // level with the LED, not further down the board
SENS_Z = SENS_AX;

module cut_mq_port(){
  translate([MQ_X, -OUT[1]/2-1, SENS_Z]) rotate([-90,0,0]){
    cylinder(h=WALL+3, d=MQ_CAN_D+0.8);                       // can passes through
    translate([0,0,WALL+1]) cylinder(h=8, d=MQ_CAN_D+3.2);    // relief behind
    cylinder(h=1.4, d1=MQ_CAN_D+3.4, d2=MQ_CAN_D+0.8);        // outer chamfer
  }
}
// DHT11 mounted ON the deck: a raised boss with an exactly 3.0 circular hole,
// a plain pad to stop it pivoting, a wire slot, and a light hole for the LED.
module cut_dht_top(){
  // ONE opening, 22.7 long overall: the blue body's window, widened, running
  // into a narrower extension that reaches the LED. Measured from the body's
  // far end to the LED, which is the number that was actually taken.
  translate([DHT_TOP_X, DHT_TOP_Y, 0]){
    body_far = DHT_BODY_Y - DHT_WIN[1]/2;          // -16.7 here
    ext_far  = body_far + DHT_OPEN_L;              // +6.0: the LED end
    ext_near = DHT_BODY_Y + DHT_WIN[1]/2;
    union(){
      translate([0, DHT_BODY_Y, OUT[2]-WALL+2])                       // body window
        hull() for(sx=[-1,1], sy=[-1,1])
          translate([sx*(DHT_WIN[0]/2-1.2), sy*(DHT_WIN[1]/2-1.2), 0])
            cylinder(h=WALL+6, r=1.2, center=true);
      translate([DHT_LED_X, (ext_near+ext_far)/2, OUT[2]-WALL+2])     // LED extension
        hull() for(sx=[-1,1], sy=[-1,1])
          translate([sx*(DHT_LED_W/2-1.2), sy*((ext_far-ext_near)/2-1.2), 0])
            cylinder(h=WALL+6, r=1.2, center=true);
    }
    translate([DHT_HOLE_X, DHT_HOLE_Y, OUT[2]-6])                     // M3 through
      cylinder(h=12, d=DHT_BOSS_HOLE);
    translate([0, DHT_HOLE_Y - 15.0, OUT[2]-WALL-4])                  // wire slot
      hull() for(sx=[-1,1]) translate([sx*(DHT_WIRE[0]/2-DHT_WIRE[1]/2), 0, 0])
        cylinder(h=12, d=DHT_WIRE[1]);
  }
}
module cut_led(){ translate([0, -OUT[1]/2-1, SENS_Z+9]) rotate([-90,0,0]) cylinder(h=WALL+3, d=3.2); }
// No boss. The DHT mount is a plain 3.50 hole through the 2.6mm deck; the
// printed tower presses into it. Nothing here exceeds 3.50.
module dht_boss(){ }
// Four pillars for the display, at the module's own 30.40 x 28.50 hole pitch.
// The board offers up from inside, sits on the pillar ends, and four M3
// self-tappers hold it. Printed deck-down these point straight up.
module oled_pillars(){
  for(sx=[-1,1], sy=[-1,1])
    translate([sx*OLED_HOLES[0]/2, -2 + sy*OLED_HOLES[1]/2, OUT[2]-WALL-OLED_PIL_H])
      cylinder(h=OLED_PIL_H, d=OLED_PIL_D);      // straight tower, no taper
}
// optional standoff rings, if the module should sit proud of the deck
// DHT tower, printed as its own little part and pressed into the deck.
//
// It cannot be moulded into the cover: the cover's only support-free
// orientation is deck-down, and anything standing proud of the deck would
// point into the build plate. Printed separately it stands up, which is free.
//
//   stem 3.4  presses into the deck's 3.5 hole
//   collar 6.0 sets how far the module sits off the deck
//   peg  3.4  enters the module's own 3.5 hole and locates it
// Straight tower, 3.40 across its whole length - under the 3.50 maximum. The
// lower half presses into the deck's 3.5 hole, the upper half locates the
// module's own 3.5 hole. No collar, so the module sits flat on the deck.
module dht_tower(){
  cylinder(h=8.0, d=3.4);
}
module dht_spacers(){
  for(i=[0,1]) translate([i*10, 0, 0]) dht_tower();        // one to fit, one spare
}

// ---- BASE ------------------------------------------------------------------
module base(){
 difference(){
  union(){
   difference(){
    union(){
      rslab([OUT[0], OUT[1], SPLIT], CORNER);                 // closed tub, floor included
      // armoured collar around the gas-sensor port
      // raised sensor boss, clipped well inside the shell so nothing is tangent
      intersection(){
        translate([MQ_X, -OUT[1]/2+1.0, SENS_Z]) rotate([-90,0,0]) cylinder(h=2.4, d=MQ_CAN_D+6);
        translate([0, 0, (FLOOR+2.4 + SPLIT-1.4)/2])
          cube([OUT[0]-2, OUT[1]+10, (SPLIT-1.4)-(FLOOR+2.4)], center=true);
      }   // collar bottom clears the body underside
    }
    // cavity
    translate([0,0,FLOOR]) rslab([IN[0], IN[1], SPLIT], CORNER-WALL);     // cavity sits on the floor
    cut_mq_port(); cut_usbc(); cut_cable();          // DHT is in the cover now
    // keyhole wall mounts through the floor
    for(sx=[-1,1]) translate([sx*30.6, 2, -0.1]) hull(){
      cylinder(h=FLOOR+0.2, d=7.6); translate([0,9,0]) cylinder(h=FLOOR+0.2, d=4.0); }
    // flank louvres
    translate([OUT[0]/2-WALL/2+0.4, -6, 13.0]) louvres(4, 16, 2.4, 5.0);
    translate([-OUT[0]/2+WALL/2-0.4, 12, 13.0]) louvres(4, 12, 2.4, 5.0);   // left: behind the DHT
    // machined detail grooves
    for(sx=[-1,1], i=[0:2]) translate([sx*(OUT[0]/2-0.6), 14, FLOOR+3+i*4.5])
      rotate([0,90,0]) cube([1.0, 12, 2.4], center=true);   // clear of the louvre field   // ends inside the flat wall, clear of the corner radius
    for(i=[0:1]) translate([0, -OUT[1]/2+0.6, FLOOR+2.5+i*3.0]) cube([46, 1.0, 1.6], center=true);
   }
   corner_bosses(SPLIT);                                     // corner webs, added after the cavity
   // interior furniture, likewise added after the cavity so it survives
      // ESP32 devkit support. The devkit is 63 long on a 50 breadboard, so
      // 6.4mm of it hangs off each end held only by its own header pins.
      // These saddles carry that overhang at exactly breadboard-top height,
      // and the lips stop the board walking sideways.
      for(sx=[-1,1]) translate([sx*30.0, BB_Y, FLOOR]){
        translate([0,0,(BB[2]-0.2)/2]) cube([6.0, 22.0, BB[2]-0.2], center=true);   // saddle
        for(sy=[-1,1]) translate([0, sy*(ESP[1]/2+1.2), BB[2]+0.8])
          cube([6.0, 1.6, 3.2], center=true);                                       // side lip
      }
      // breadboard mount: 4 corner brackets, board drops in and is captive
      for(sx=[-1,1], sy=[-1,1]) translate([sx*(BB[0]/2+0.3), BB_Y+sy*(BB[1]/2+0.3), FLOOR]){
        translate([-sx*4.0, 0, 0]) cube([9.6, 1.8, 4.2], center=false ? false : true)
          ;                                            // leg along X
        translate([0, -sy*4.0, 0]) cube([1.8, 9.6, 4.2], center=true);   // leg along Y
      }
      // thin pad so the board sits above the floor texture
      translate([0, BB_Y, FLOOR+0.4]) cube([BB[0]-8, BB[1]-8, 0.8], center=true);
      translate([MQ_X,  -IN[1]/2+4.0, FLOOR+0.45]) cube([MQ_PCB[0]+2, 8, 0.9], center=true);

  }
  // self-tap pilot for M3 x 5 -- 3.0mm of thread, no insert needed
  for(sx=[-1,1], sy=[-1,1])
    translate([sx*(OUT[0]/2-BOSS_R-BOSS_IN), sy*(OUT[1]/2-BOSS_R-BOSS_IN), SPLIT-6.5])
      cylinder(h=6.6, d=2.5);
 }
}

// ---- BOTTOM COVER ---------------------------------------------------------
module plate(){
  difference(){
    union(){
      rslab([OUT[0], OUT[1], PLATE_T], CORNER);
      // register lip that drops into the body
      translate([0,0,PLATE_T-0.01]) rslab([IN[0]-2*PLATE_CLR, IN[1]-2*PLATE_CLR, 2.0], CORNER-WALL-PLATE_CLR);
      // sensor supports: module PCBs rest on these, heights from the audit
      translate([MQ_X,  -IN[1]/2+4.0, PLATE_T+0.25]) cube([MQ_PCB[0]+2, 8, 0.5], center=true);   // MQ PCB bottom z=3.5
      translate([DHT_X, -IN[1]/2+4.0, PLATE_T+2.75]) cube([DHT_PCB[0]+2, 8, 5.5], center=true);  // DHT PCB bottom z=8.5
      // breadboard seat, raised so the board clears the screw heads
      translate([0, BB_Y, PLATE_T+0.4]) cube([BB[0]+6, BB[1]+6, 1.6], center=true);
    }
    // breadboard recess in that seat
    translate([0, BB_Y, PLATE_T+1.4]) cube([BB[0]+0.6, BB[1]+0.6, 1.8], center=true);
    // 4 countersunk M3 into the posts above
    for(sx=[-1,1], sy=[-1,1])
      translate([sx*(OUT[0]/2-BOSS_R-BOSS_IN), sy*(OUT[1]/2-BOSS_R-BOSS_IN), -0.1]){
        cylinder(h=PLATE_T+3, d=3.3);
        cylinder(h=1.9, d1=6.4, d2=3.3);                        // countersink, sits flush
      }
    // clearance so the register lip does not fight the corner posts
    for(sx=[-1,1], sy=[-1,1])
      translate([sx*(OUT[0]/2-BOSS_R-BOSS_IN), sy*(OUT[1]/2-BOSS_R-BOSS_IN), PLATE_T])
        cylinder(h=4, r=BOSS_R+0.3);
    // keyhole wall mounts
    for(sx=[-1,1]) translate([sx*20, -6, -0.1]) hull(){
      cylinder(h=PLATE_T+0.2, d=7.6); translate([0,-8,0]) cylinder(h=PLATE_T+0.2, d=4.0); }
    // cable-tie slots for strain relief
    for(sx=[-1,1]) translate([sx*10, 20, PLATE_T/2]) cube([3.2, 8, PLATE_T+2], center=true);
  }
}

// ---- COVER -----------------------------------------------------------------
COVER_H = OUT[2] - SPLIT;
module cover(){
  difference(){
    union(){
      translate([0,0,SPLIT]) rslab_ch([OUT[0], OUT[1], COVER_H], CORNER, 2.0);
      corner_pads();
    }
    // inner shell
    translate([0,0,SPLIT-0.01]) rslab([IN[0], IN[1], COVER_H-2.2], CORNER-WALL);
    // display: window -> glass relief -> PCB pocket (stepped, module drops in from below)
    translate([0,-2,OUT[2]-WALL]){
      // STRAIGHT window. It used to flare 1.3mm per side over 4.4mm, which
      // read as a fat lip around the glass and ate into the bezel groove.
      translate([0,0,3]) cube([OLED_GLASS[0], OLED_GLASS[1], 8], center=true);
      // clearance for the board itself; the pillars do the holding
      translate([0,0,-2.6]) cube([OLED_PCB[0]+0.7, OLED_PCB[1]+0.7, 4.2], center=true);
    }
    corner_screws(SPLIT+0.2, true);
    corner_pad_cuts();
    // top exhaust louvres behind the screen
    translate([0, OUT[1]/2-10, OUT[2]-2]) top_slots(6, 11, 2.2, 4.6);   // 2.6mm of deck left below the window
    // bezel groove: cut, not raised, so the deck prints flat face-down
    translate([0, -2, OUT[2]-0.8])
      difference(){
        rslab([OLED_GLASS[0]+11, OLED_GLASS[1]+11, 2], 3.4);
        translate([0,0,-0.1]) rslab([OLED_GLASS[0]+7.6, OLED_GLASS[1]+7.6, 3], 2.6);
      }
    cut_led();
    // ventilation beside the display, like the reference top cover
    translate([30.0, -4, OUT[2]-2]) top_slots(3, 16, 2.0, 4.2);   // right only: the
    cut_dht_top();                                               // left strip is the DHT now
  }
  dht_boss();      // union'd on afterwards so the recess cut cannot erase it
  oled_pillars();  // likewise: four posts for the display to screw onto
}

// ---- dummy components (renders only) ---------------------------------------
module parts(z=0){
  translate([0,0,z]){
    color("#e8e4d8") translate([0, BB_Y, FLOOR]) cube([BB[0], BB[1], BB[2]], center=true);
    color("#1b1b1b") translate([0, BB_Y, FLOOR+BB[2]/2+ESP[2]/2]) cube([ESP[0], ESP[1], ESP[2]], center=true);
    color("#123a6e") translate([DHT_TOP_X, DHT_TOP_Y-4, OUT[2]+0.8])
      cube([13.5, 32.0, 1.6], center=true);                       // carrier, on the boss
    color("#2f8ad6") translate([DHT_TOP_X, DHT_TOP_Y+DHT_BODY_Y-4, OUT[2]+4.4])
      cube([DHT_BODY2[0], DHT_BODY2[1], 5.5], center=true);       // blue body
    color("#c62828") translate([DHT_TOP_X+DHT_LED_X, DHT_TOP_Y+DHT_LED_Y-4, OUT[2]+1.6])
      cylinder(h=2.4, d=3.0);                                     // red power LED
    color("#8f9296") translate([MQ_X, -OUT[1]/2-4.0, SENS_Z]) rotate([-90,0,0]) cylinder(h=9.5, d=MQ_CAN_D);
    color("#6c7076") translate([MQ_X, -OUT[1]/2-4.1, SENS_Z]) rotate([-90,0,0]) cylinder(h=0.9, d=MQ_CAN_D+1.8);
    color("#0a3d2e") translate([0,-2,OUT[2]-WALL-3.3]) cube([OLED_PCB[0], OLED_PCB[1], OLED_PCB[2]], center=true);
    color("#111") translate([0,-2,OUT[2]-WALL-1.0]) cube([OLED_PANEL[0], OLED_PANEL[1], 1.8], center=true);
    color("#0d2b6b") translate([0,-2,OUT[2]-WALL-0.2]) cube([OLED_GLASS[0], OLED_GLASS[1], 0.6], center=true);
  }
}

// ---- output ----------------------------------------------------------------
module clamp(){
  difference(){
    union(){
      cube([OLED_PCB[0]+9, 6, 3.0], center=true);
      for(sx=[-1,1]) translate([sx*(OLED_PCB[0]/2+3.0),0,0]) cylinder(h=3.0, d=7.5, center=true);
    }
    for(sx=[-1,1]) translate([sx*(OLED_PCB[0]/2+3.0),0,0]) cylinder(h=6, d=2.2, center=true);
  }
}
if(mode==8){ color("#4a5138") base(); parts(); }     // base + electronics, lid off
else if(mode==7){                      // assembled cross-section
  difference(){
    union(){ color("#4a5138") base(); color("#3e4530") cover(); parts(); }
    translate([0,-100,-10]) cube([200,100,120]);      // cut away the front half
  }
}
else if(mode==4) translate([0,0,1.5]) clamp();
else if(mode==10) dht_spacers();
else if(mode==5) plate();

else if(mode==0){ color("#4a5138") base(); color("#3e4530") cover(); parts(); }
else if(mode==1) color("#4a5138") base();
else if(mode==6){ color("#4a5138") base(); color("#3e4530") plate(); }
else if(mode==2)                       // print orientation: deck DOWN, no support
  translate([0,0,OUT[2]]) rotate([180,0,0]) color("#3e4530") cover();
else if(mode==9)                       // as-assembled, for renders
  translate([0,0,-SPLIT]) color("#3e4530") cover();
else {
  translate([0,0,-16]) color("#39402c") plate();
  color("#4a5138") base();
  parts(EXPLODE*0.18);
  translate([0,0,EXPLODE]) color("#3e4530") cover();
}
