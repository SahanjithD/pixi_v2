## Priority 0: Survival 
The robot ignores everything else to stay "alive".

EMERGENCY_SHUTDOWN (Originally GO_TO_SLEEP)

Definition: Immediate power preservation mode.

Precondition: energy < 0.15 (15% Battery).

Effect: Stop motors immediately. Display "Low Battery" icon. Dim screen to minimum. Refuse to wake up until charged.


## Priority 1: Reflexes

**AVOID_OBSTACLE**


Definition: Immediate stop or swerve when a proximity sensor/depth camera detects a blockage < 20cm.

Precondition: obstacle_distance < threshold.

Effect: Stop motors, reverse 5cm, turn random 30°.


**BACK_AWAY_SCARED**


Definition: Rapid retreat caused by sudden loud noises or fast-approaching objects.

Precondition: caution_level > 0.8 OR sudden_motion_detected.

Effect: Drive backward fast, play "whimper" sound, display "wide eyes" on screen.



## Priority 2: Social Interaction

**ENJOY_TOUCH**

Definition: Reacting to physical affection.

Precondition: touch_sensor_is_active == True.

Effect: Stop motors (don't drive away while being petted!). Close eyes (happy animation). Play "purr" or "coo" sound.

State Change: Rapidly decreases caution. Increases energy slightly.

**GREET_HAPPILY**

Definition: A "first contact" reaction when a person appears.

Precondition: face_visible == True AND time_since_last_greeting > 5 mins.

Effect: Face lights up green/yellow, small "chirp"

Inspiration: EMO's "Good Morning" and Vector's "Hey there" animation.


**FOLLOW_PERSON**

Definition: Active tracking to keep the user in the "Social Zone" (approx. 1 meter away).

Precondition: face_visible == True.

Effect: PID control loop to keep face center-frame. If face area < 10% (too far), drive forward. If face area > 30% (too close), stop.

Inspiration: Loona’s "Follow Me" mode.

**SEARCH_FOR_HUMAN**

Definition: Active patrolling to find a friend when lonely.

Precondition: attention_hunger > 0.7 AND face_visible == False.

Effect: Spin 60° slowly left and right. If no face found, go to sleep by 20 seconds.

Inspiration: Vector's autonomous exploring when looking for faces.

## Priority 3: Play & Expression

**DO_A_HAPPY_DANCE**

Definition: A high-energy celebration.

Precondition: excitement > 0.8 AND energy > 0.5.

Effect: Spin in circles, play upbeat MIDI/sound.

Inspiration: EMO unlocking new dance moves as he "grows up".

**WIGGLE_EXCITEDLY**

Definition: A lower-energy version of the dance (stationary).

Precondition: excitement > 0.6.

Effect: Rapid left-right body twitch (shimmy), happy "humming" sound.

## Priority 4: Idle & Restoration


**LOOK_AROUND**

Definition: Passive observation.

Precondition: curiosity > 0.5 OR boredom > 0.6.

Effect: Pan head slowly (-45° to +45°), blink eyes randomly.

Inspiration: Vector's idle animations where he observes his environment.

**GO_TO_SLEEP**

Definition: Battery saving mode.

Precondition: energy < 0.2 (Low Battery) OR boredom > 0.9 (Ignored for too long).

Effect: Crouch down, dim screen to "Zzz" animation, disable motor torque.

Inspiration: Vector driving to charger or sleeping when ignored.


