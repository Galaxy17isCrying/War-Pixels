CAMPAIGN_MISSIONS = (
    dict(codename="FIRST LIGHT", name="The Last Convoy", mode="ctf", map="depot_09", briefing="An allied supply convoy has gone dark inside Depot 09. Recover its signal key before the enemy can move it.", objective="Capture the enemy flag three times.", recommended="NORMAL"),
    dict(codename="SHIFTING SANDS", name="Dustline", mode="hardpoint", map="dustline", briefing="The signal key points to a relay hidden in the desert. Hold the relay long enough to extract its data.", objective="Control the rotating hardpoint and reach the score limit.", recommended="NORMAL"),
    dict(codename="GHOST SIGNAL", name="Blacksite Breach", mode="snd", map="blacksite", briefing="A covert transmission leads to a sealed research facility. Plant the charge and destroy the archive.", objective="Win rounds by planting the bomb or eliminating the opposing squad.", recommended="HARD"),
    dict(codename="IRON VEIL", name="District Lockdown", mode="ctf", map="iron_district", briefing="The archive identifies an enemy command post. Break through the perimeter and seize its battle plans.", objective="Capture the enemy flag three times.", recommended="HARD"),
    dict(codename="COLD FRONT", name="Whiteout Protocol", mode="hardpoint", map="summitline", briefing="A blizzard is masking an enemy weapons transfer. Take the mountain relay before the convoy escapes.", objective="Hold the hardpoint and reach the score limit.", recommended="HARD"),
    dict(codename="BURNING SKY", name="Crash Landing", mode="ctf", map="crashsite", briefing="Friendly aircraft has been downed in hostile territory. Secure the crash site and recover the flight recorder.", objective="Eliminate hostile forces and reach the team score limit.", recommended="HARD"),
    dict(codename="NO SAFE HOUSE", name="Town of Shadows", mode="snd", map="standoff", briefing="Intercepted orders point to a weapons cache hidden in a border town. Deny the enemy access to the cache.", objective="Defend the site or plant the charge to win the round.", recommended="ELITE"),
    dict(codename="LAST TRAINING", name="Live-Fire", mode="hardpoint", map="firing_range", briefing="The enemy has occupied a training facility to prepare its final assault. Push through the lanes and disable its command uplink.", objective="Control the rotating hardpoint and reach the score limit.", recommended="ELITE"),
    dict(codename="FINAL HOUR", name="Nuketown Showdown", mode="ctf", map="nuketown", briefing="The final transmission leads to a fortified residential block. Stop the enemy commander before extraction begins.", objective="Reach the team score limit and finish the operation.", recommended="ELITE"),
)

def campaign_mission(index):
    if not isinstance(index, int) or not 0 <= index < len(CAMPAIGN_MISSIONS):
        raise ValueError(f"Unknown campaign mission index: {index}")
    return CAMPAIGN_MISSIONS[index]
