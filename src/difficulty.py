DIFFICULTIES = {
    "EASY": dict(reaction=0.85, aim_err=16.0, aim_tolerance=0.8, turn=170.0, tactics=0.25, aggression=0.4,
                 ability=0.25, share=0.0, lead=0.0, burst=3, hear_err=220.0, view=520.0, retreat_hp=0.4,
                 cover=0.15, desc="Slow reactions, loose aim, poor tactics."),
    "NORMAL": dict(reaction=0.5, aim_err=9.0, aim_tolerance=0.7, turn=270.0, tactics=0.6, aggression=0.6,
                   ability=0.6, share=1.0, lead=0.15, burst=5, hear_err=120.0, view=600.0, retreat_hp=0.3,
                   cover=0.55, desc="Balanced aim, basic teamwork and cover."),
    "HARD": dict(reaction=0.28, aim_err=5.0, aim_tolerance=0.65, turn=400.0, tactics=0.85, aggression=0.75,
                 ability=0.85, share=1.0, lead=0.4, burst=8, hear_err=70.0, view=640.0, retreat_hp=0.28,
                 cover=0.8, desc="Fast reactions, recoil control, flanking."),
    "ELITE": dict(reaction=0.16, aim_err=3.5, aim_tolerance=0.6, turn=560.0, tactics=1.0, aggression=0.9,
                  ability=1.0, share=1.0, lead=0.65, burst=12, hear_err=40.0, view=680.0, retreat_hp=0.25,
                  cover=1.0, desc="Sharp tactics and teamwork. Fair, not omniscient."),
}
ORDER = ["EASY", "NORMAL", "HARD", "ELITE"]
