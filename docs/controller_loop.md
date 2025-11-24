```mermaid
graph TD
    Root[("ROOT TICK (30Hz)")] --> SurvivalCheck{{"? Battery < 15%"}}
    
    %% PRIORITY 0: SURVIVAL
    SurvivalCheck -- YES --> Shutdown[("Action: EMERGENCY_SHUTDOWN")]
    
    %% PRIORITY 1: AUDIO (The "Freeze" Command)
    SurvivalCheck -- NO --> AudioCheck{{"? Hotword 'Hey Pixi' Active"}}
    AudioCheck -- YES --> Listen[("Action: LISTEN_TO_USER\n(Stop Motors, Record Audio)")]
    
    %% PRIORITY 2: TOUCH (The "Pause" Command)
    AudioCheck -- NO --> TouchCheck{{"? Touch Sensor Active"}}
    TouchCheck -- YES --> Enjoy[("Action: ENJOY_TOUCH\n(Stop, Purr, Close Eyes)")]
    
    %% PRIORITY 3: SAFETY REFLEXES
    TouchCheck -- NO --> SafetyCheck{{"? Obstacle < 20cm"}}
    SafetyCheck -- YES --> Avoid[("Action: AVOID_OBSTACLE")]
    
    %% PRIORITY 4: UTILITY AI (The "Choice")
    SafetyCheck -- NO --> UtilitySel[("? Utility Selector")]
    UtilitySel --> CalcScores["Calculate Scores based on\nEnergy, Hunger, Boredom"]
    CalcScores --> PickWinner["Pick Highest Score"]
    
    %% DYNAMIC BEHAVIORS
    PickWinner -- "Winner: FOLLOW" --> RunFollow[("Execute: FOLLOW_PERSON")]
    PickWinner -- "Winner: SEARCH" --> RunSearch[("Execute: SEARCH_FOR_HUMAN")]
    PickWinner -- "Winner: DANCE" --> RunDance[("Execute: DO_A_HAPPY_DANCE")]
    PickWinner -- "Winner: NAP" --> RunNap[("Execute: NAP_TIME")]


    ```