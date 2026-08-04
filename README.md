# "Whack A Mole" Full-body Game

ENGG3000 has tasked its students to design a build a full body "Whack a Mole" game in which "moles" randomly appear on a video screen. The player positions a cursor on the screen by moving their physical body in front of the screen with the system tracking their position using ultrasonic sensors installed into a lunchbox. If the player moves their body over the "mole" before it disappears, they score a point, otherwise, a new mole pops up somewhere new.

## 1.1 Subsystems
<ul>
  <li><strong>Software</strong>
    <ol>
      <li>Python and Pygame </li>
    </ol>
  </li>
  <li><strong>Hardware</strong>
    <ol>
        <li>ESP32U</li>
        <li>UltraSonic: RCWL-1601</li>
    </ol>
  </li>
</ul>

## 1.2 Constraints
<ol>
  <li><strong>CON-01</strong>  : 3m x 3m play area  </li>
  <li><strong>CON-02</strong>  : no system components placed inside the 3m x 3m play area </li>
  <li><strong>CON-03</strong>  : each box enclosure is no larger than 100x 100 x 50mm </li>
  <li><strong>CON-04</strong>  : using 3 x AA Nickel battery, and operates more than one hour </li>
  <li><strong>CON-05</strong>  : rechargeable from a USB-A power source </li>
  <li><strong>CON-06</strong>  : $100 budget</li>
  <li><strong>CON-07</strong>  : the software is downloadable and installable on a Window computers / desktop app version</li>
  <li><strong>CON-08</strong>  : supplied components are not directly altered </li>
  <li><strong>SAF-01</strong>  : An audible alarm and effective visual warning activate when the player is within 50cm of the screen</li>
</ol>

## 1.3 Requirement 
**Note: FR : functional requiremnet and NFR : nonfunctional requirement , and SAF is for safety 

| ID     | Priority | Requirement                                                                 | Source          |
|--------|----------|-----------------------------------------------------------------------------|-----------------|
| FR-01  | Must     | The system tracks the player's position over the approved 3 m × 3 m area.   | Brief           |
| FR-02  | Must     | Sensor data is transmitted wirelessly to the Windows laptop or approved receiver path. | Brief           |
| FR-03  | Must     | The cursor follows player movement without a handheld controller.           | Product vision  |
| FR-04  | Must     | A point is awarded only when the cursor reaches an active mole.             | Brief           |
| FR-05  | Must     | The game provides multiple selectable difficulty levels with measurable differences. | Brief           |
| FR-06  | Must     | The system provides a calibration workflow before normal play.              | Derived         |
| FR-07  | Must     | The game supports ready, countdown, active, paused, tracking-lost, and finished states. | Derived         |
| FR-08  | Must     | The player receives visible and audible hit, miss, warning, and session feedback. | Derived         |
| FR-09  | Must     | Invalid, stale, or missing sensor data does not create a score or unsafe cursor jump. | Derived         |
| FR-10  | Should   | The game records session score, level, duration, and selected quality data. | Project goal    |
| FR-11  | Should   | The final game presents a 2D playfield while preserving verified gameplay rules. | Team goal       |
| FR-12  | Could    | The player can view a local session-best score.                             | Gamer value     |
| NFR-01 | Must     | Tracking is accurate and responsive enough for fair gameplay.               | Brief           |
| NFR-02 | Must     | The game remains stable through loss and recovery of one sensor node.       | Derived         |
| NFR-03 | Must     | Software starts on the assessment Windows laptop without a development environment. | Brief           |
| SAF-01 | Must     | Audible and effective visual warnings activate within 50 cm of the screen.  | Brief           |
| SAF-02 | Must     | Scoring pauses when safety warning or tracking-lost state is active.        | Derived         |
