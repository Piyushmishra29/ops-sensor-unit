// ===========================================================================
// OPS SENSOR UNIT — ESP32 environmental monitor
// mode: 0 assembly | 1 base only | 2 cover only | 3 exploded
// ===========================================================================
mode = 0;
$fn = 40;

// ---- real component data --------------------------------------------------
BB      = [50.14, 38.54, 6.50];   // mini breadboard (bread.stl, measured)
ESP     = [63.0, 25.5, 13.0];     // ESP32-S3 DevKitC seated on the breadboard
OLED_PCB   = [35.5, 33.5, 1.6];   // 1.3" SH1106 module carrier board
OLED_PANEL = [34.8, 23.2];        // MEASURED glass panel outline
OLED_GLASS = [34.8, 25.8];        // SCREEN CUTOUT as specified (panel 34.8 x 23.2)
OLED_HOLES = [30.5, 28.5];        // M2 pitch  << still to confirm
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
      translate([0,0,z0]) cylinder(h=40, d=3.3);                        // M3 shank clearance
      if(deep){
        translate([0,0,OUT[2]-7.6]) cylinder(h=9, d=6.4);               // head well, 7.6 deep
        translate([0,0,OUT[2]-8.5]) cylinder(h=1.0, d1=3.3, d2=6.4);
      }
    }
}
// recessed corner pads on the top deck - the rugged tell
module corner_pads(){
  for(sx=[-1,1], sy=[-1,1])
    translate([sx*(OUT[0]/2-BOSS_R-BOSS_IN), sy*(OUT[1]/2-BOSS_R-BOSS_IN), OUT[2]-1.2])
      difference(){ cylinder(h=1.6, r=BOSS_R+0.6); cylinder(h=2, r=BOSS_R-0.9); }
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
DHT_Y = -6.0;     // DHT11 moved to the LEFT FLANK: no room beside the MQ on the front wall
SENS_Z = SENS_AX;

module cut_mq_port(){
  translate([MQ_X, -OUT[1]/2-1, SENS_Z]) rotate([-90,0,0]){
    cylinder(h=WALL+3, d=MQ_CAN_D+0.8);                       // can passes through
    translate([0,0,WALL+1]) cylinder(h=8, d=MQ_CAN_D+3.2);    // relief behind
    cylinder(h=1.4, d1=MQ_CAN_D+3.4, d2=MQ_CAN_D+0.8);        // outer chamfer
  }
}
module cut_dht_port(){                       // in the LEFT wall now
  translate([-OUT[0]/2-1, DHT_Y, SENS_Z]) rotate([0,90,0])
    hull() for(sy=[-1,1], sz=[-1,1])
      translate([sy*(DHT_BODY[0]/2-1.5), sz*(DHT_BODY[1]/2-1.5), 0]) cylinder(h=WALL+4, r=1.9);
}
module cut_usbc(){
  translate([OUT[0]/2-1, 8, FLOOR+9.7]) rotate([0,90,0])   // z=12.3 = devkit USB-C centre   // y=8: clears the rear post by 8.3
    hull() for(sx=[-1,1]) translate([sx*3.0, 0, 0]) cylinder(h=WALL+4, d=7.4);
}
module cut_led(){ translate([0, -OUT[1]/2-1, SENS_Z+9]) rotate([-90,0,0]) cylinder(h=WALL+3, d=3.2); }
module cut_cable(){                        // rear-corner cable pass
  translate([-18, OUT[1]/2-1, FLOOR+6]) rotate([90,0,0]) cylinder(h=WALL+4, d=8);  // x=-18: clears the rear-left post by 3.5
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
    cut_mq_port(); cut_dht_port(); cut_usbc(); cut_cable();
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
      // breadboard mount: 4 corner brackets, board drops in and is captive
      for(sx=[-1,1], sy=[-1,1]) translate([sx*(BB[0]/2+0.3), BB_Y+sy*(BB[1]/2+0.3), FLOOR]){
        translate([-sx*4.0, 0, 0]) cube([9.6, 1.8, 4.2], center=false ? false : true)
          ;                                            // leg along X
        translate([0, -sy*4.0, 0]) cube([1.8, 9.6, 4.2], center=true);   // leg along Y
      }
      // thin pad so the board sits above the floor texture
      translate([0, BB_Y, FLOOR+0.4]) cube([BB[0]-8, BB[1]-8, 0.8], center=true);
      translate([MQ_X,  -IN[1]/2+4.0, FLOOR+0.45]) cube([MQ_PCB[0]+2, 8, 0.9], center=true);
      translate([-IN[0]/2+4.0, DHT_Y, FLOOR+2.95]) cube([8, DHT_PCB[0]+2, 5.9], center=true);

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
      // raised bezel frame around the screen
      translate([0, -2, OUT[2]-0.4])
        rslab([OLED_GLASS[0]+11, OLED_GLASS[1]+11, 1.6], 3.4);
      corner_pads();
    }
    // inner shell
    translate([0,0,SPLIT-0.01]) rslab([IN[0], IN[1], COVER_H-2.2], CORNER-WALL);
    // display: window -> glass relief -> PCB pocket (stepped, module drops in from below)
    translate([0,-2,OUT[2]-WALL]){
      hull(){                                                       // chamfered window
        cube([OLED_GLASS[0], OLED_GLASS[1], 0.1], center=true);
        translate([0,0,WALL+1.8]) cube([OLED_GLASS[0]+2.6, OLED_GLASS[1]+2.6, 0.1], center=true);
      }
      translate([0,0,3]) cube([OLED_GLASS[0], OLED_GLASS[1], 8], center=true);
      translate([0,0,-2.6]) cube([OLED_PCB[0]+0.7, OLED_PCB[1]+0.7, 4.2], center=true);      // PCB pocket: module loads from below, rests on the Y ledges
      for(sx=[-1,1], sy=[-1,1])
        translate([sx*OLED_HOLES[0]/2, sy*OLED_HOLES[1]/2, -3]) cylinder(h=10, d=2.2, center=true);
    }
    corner_screws(SPLIT+0.2, true);
    // top exhaust louvres behind the screen
    translate([0, OUT[1]/2-10, OUT[2]-2]) top_slots(6, 11, 2.2, 4.6);   // 2.6mm of deck left below the window
    cut_led();
    // ventilation beside the display, like the reference top cover
    for(sx=[-1,1]) translate([sx*30.0, -4, OUT[2]-2]) top_slots(3, 16, 2.0, 4.2);
  }
}

// ---- dummy components (renders only) ---------------------------------------
module parts(z=0){
  translate([0,0,z]){
    color("#e8e4d8") translate([0, BB_Y, FLOOR]) cube([BB[0], BB[1], BB[2]], center=true);
    color("#1b1b1b") translate([0, BB_Y, FLOOR+BB[2]/2+ESP[2]/2]) cube([ESP[0], ESP[1], ESP[2]], center=true);
    color("#2f8ad6") translate([-OUT[0]/2-0.8, DHT_Y, SENS_Z])
      rotate([0,90,0]) cube([DHT_BODY[0], DHT_BODY[1], DHT_BODY[2]], center=true);
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
else if(mode==5) plate();
else if(mode==4) clamp();
else if(mode==0){ color("#4a5138") base(); color("#3e4530") cover(); parts(); }
else if(mode==1) color("#4a5138") base();
else if(mode==6){ color("#4a5138") base(); color("#3e4530") plate(); }
else if(mode==2) translate([0,0,-SPLIT]) color("#3e4530") cover();
else {
  translate([0,0,-16]) color("#39402c") plate();
  color("#4a5138") base();
  parts(6);
  translate([0,0,34]) color("#3e4530") cover();
}
