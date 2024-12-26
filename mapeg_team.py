import pandas as pd
import numpy as np
import json
import random
from datetime import datetime, timedelta
from enum import Enum

class history_options(Enum):
    MEMBER_HISTORY = 1
    PAIRING_HISTORY = 2
    TEAM_ID_COUNTER = 3



class MAPEGTeamAssignment:
    # Excel file paths
    mali_uzmanlar_path = 'mali uzman ve harita mühendisi diğer.xlsx'
    maden_uzmanlari_path = 'MEVCUT YERALTI MADEN UZMANLARI VE GÖREVLERİ düzenli fp.xlsx'

    # Read excel files
    mali_uzmanlar_df = pd.read_excel(mali_uzmanlar_path)
    maden_uzmanlari_df = pd.read_excel(maden_uzmanlari_path)

    # Data preprocessing
    maden_uzmanlari_df['Mesleği'] = maden_uzmanlari_df['Mesleği'].str.strip()
    maden_uzmanlari_df.columns = maden_uzmanlari_df.columns.str.strip()
    maden_uzmanlari_df = maden_uzmanlari_df.drop(columns='Unnamed: 9')

    # Seperate members based on their proffessions
    members = {
        'maden_muhendisleri': maden_uzmanlari_df[maden_uzmanlari_df['Mesleği'] == 'Maden'],
        'jeoloji_muhendisleri': maden_uzmanlari_df[maden_uzmanlari_df['Mesleği'] == 'Jeoloji'],
        'mali_uzmanlari': mali_uzmanlar_df[mali_uzmanlar_df['UNVAN'] == 'Mali Uzman Y.'],
        'harita_muhendisleri': mali_uzmanlar_df[mali_uzmanlar_df['UNVAN'] == 'Harita Mühendisi'],
        'insaat_muhendisleri': mali_uzmanlar_df[mali_uzmanlar_df['UNVAN'] == 'İnşaat Mühendisi'],
        'maden_teknikeri': mali_uzmanlar_df[mali_uzmanlar_df['UNVAN'] == 'Maden Teknikeri'],
        'jeofizik_muhendisleri': mali_uzmanlar_df[mali_uzmanlar_df['UNVAN'] == 'Jeofizik Mühendisi'],
        'makina_muhendisleri': mali_uzmanlar_df[mali_uzmanlar_df['UNVAN'] == 'Makina Mühendisi'],
        'elektrik_elektronik_muhendisleri': mali_uzmanlar_df[mali_uzmanlar_df['UNVAN'] == 'Elektrik Elektronik Mühendisi'],
        'makina_teknikeri': mali_uzmanlar_df[mali_uzmanlar_df['UNVAN'] == 'Makina Teknikeri']
    }

    # Target cities
    target_cities = [
        "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Aksaray", "Amasya", "Ankara", "Antalya", "Ardahan", "Artvin",
        "Aydın", "Balıkesir", "Bartın", "Batman", "Bayburt", "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur",
        "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli", "Diyarbakır", "Düzce", "Edirne", "Elazığ", "Erzincan",
        "Erzurum", "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane", "Hakkâri", "Hatay", "Iğdır", "Isparta", "İstanbul",
        "İzmir", "Kahramanmaraş", "Karabük", "Karaman", "Kars", "Kastamonu", "Kayseri", "Kırıkkale", "Kırklareli",
        "Kırşehir", "Kilis", "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", "Mardin", "Mersin", "Muğla", "Muş",
        "Nevşehir", "Niğde", "Ordu", "Osmaniye", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas",
        "Şanlıurfa", "Şırnak", "Tekirdağ", "Tokat", "Trabzon", "Tunceli", "Uşak", "Van", "Yalova", "Yozgat", "Zonguldak"
    ]

    # JSON file for team history and current teams
    history_file = 'team_history.json'
    created_teams_file = 'created_teams.json'

    def __init__(self):
        pass

    @classmethod
    def load_team_history(cls, option: history_options = None, **kwargs):
        try:
            with open(cls.history_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
                match option:
                    case history_options.MEMBER_HISTORY:
                        if kwargs is None:
                            return data.get("member_history", {})
                        elif "member_id" in kwargs.keys():
                            member_id = kwargs["member_id"]
                            if str(member_id) in data["member_history"].keys():
                                return data["member_history"][str(member_id)]
                            else:
                                raise ValueError(f"MAPEGTeamAssignment.load_team_history(): There is not a member having ID = {member_id}")
                    case history_options.PAIRING_HISTORY:
                        return data.get("pairing_history", {})
                    case history_options.TEAM_ID_COUNTER:
                        return data.get("team_id_counter", 1)
                    case None:
                        return data.get("member_history", {}), data.get("pairing_history", {}), data.get("team_id_counter", 1)
                    case _:
                        raise TypeError(f"MAPEGTeamAssignment.load_team_history(): Invalid history option '{option}'")

        except (FileNotFoundError, json.JSONDecodeError):
            return {}, {}, 0


    @classmethod
    def select_member(cls, key: str, car_usage: bool) -> dict:
        member_key = 'Sıra No' if key != "mali_uzmanlari" else 'ID'

        remaining_members = []
        for i in range(len(list(cls.members[key][member_key]))):
            member_dict = dict(cls.members[key].iloc[i])
            # NumPy tiplerini Python built-in tiplerine dönüştürme
            for k, v in member_dict.items():
                if isinstance(v, np.int64):
                    member_dict[k] = int(v)
                elif isinstance(v, np.float64):
                    member_dict[k] = float(v)
            remaining_members.append(member_dict)


        for _ in range(len(list(cls.members[key][member_key]))):
            # Shuffle the members
            random.shuffle(remaining_members)

            # Select the random member
            member = remaining_members.pop()

            # Load the member history
            member_history = cls.load_team_history(
                history_options.MEMBER_HISTORY,
                member_id=member[member_key]
            )

            if (
                member_history['when_available'] is None or
                (
                    (
                        datetime.now() -
                        datetime.strptime(
                            member_history['when_available'],
                            "%Y-%m-%dT%H:%M:%S.%f"
                        )
                    ).total_seconds() > 0
                )
            ) and (
                not car_usage or
                car_usage and (
                    (
                        key == "mali_uzmanlari" and
                        (
                            member['ARAÇ KULLANABİLİR'] == "Evet" or
                            member['ARAÇ KULLANABİLİR'] == "E"
                        )
                    ) or
                    (
                        key != "mali_uzmanlari" and
                        (
                            member['Araç Kullanımı'] == "Manuel" or
                            member['Araç Kullanımı'] == "Otomatik"
                        )
                    )
                )
            ):
                break

            member = None

        return member


    """
    @classmethod
    def add_new_team_to_created_teams(cls, team: dict):
        try:
            # Load existing data
            with open(cls.created_teams_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            # If file doesn't exist or is malformed, start with a fresh structure
            data = {}

        # Make sure 'teams' is a list in our data
        if 'teams' not in data or not isinstance(data['teams'], list):
            print("asdasdadasdasdasdasda")
            data['teams'] = []

        # Append the new team dictionary
        data['teams'].append(team)

        # Write updated data back to the file
        with open(cls.created_teams_file, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=4)
    
    """


    @classmethod
    def add_new_team_to_created_teams(cls, team: dict):
        try:
            with open(cls.created_teams_file, 'r', encoding='utf-8') as file:
                data = json.load(file)

            data['teams'].append(team)
            data['total_teams'] = len(data['teams'])  # total_teams'i güncelle

            with open(cls.created_teams_file, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=4)

        except (FileNotFoundError, json.JSONDecodeError):
            pass

    @classmethod
    def create_team(cls, target_city: str = None, end_date: datetime = None) -> dict:
        print("deneme")
        try:
            members = []

            # Create list of initial member types we need
            member_types = ['maden_muhendisleri', 'jeoloji_muhendisleri', 'mali_uzmanlari']

            for i, key in enumerate(member_types):
                # Check car usage requirement for mali uzmanlar based on existing team members
                if key == "mali_uzmanlari":
                    car_users = [
                        member.get("Araç Kullanımı") in ["Manuel", "Otomatik"]
                        for member in members
                    ]
                    needs_car_user = not any(car_users)
                    member = cls.select_member(key=key, car_usage=needs_car_user)
                else:
                    # Random car usage requirement for other member types
                    member = cls.select_member(key=key, car_usage=random.choice([True, False]))

                if member is None:
                    return {}
                members.append(member)

            # Load total teams count
            try:
                with open(cls.created_teams_file, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    total_teams = data.get('total_teams', 0)
            except (FileNotFoundError, json.JSONDecodeError):
                total_teams = 0

            # Create team dictionary
            team = {
                "team_id": cls.load_team_history(history_options.TEAM_ID_COUNTER) + total_teams + 1,
                "target_city": target_city,
                "members": members,
                "end_date": end_date.isoformat() if end_date else datetime.now().isoformat()
            }

            cls.add_new_team_to_created_teams(team)

            return team

        except Exception as e:
            print(f"Error creating team: {str(e)}")
            return {}

    @classmethod
    def update_created_teams(cls, team_id: int, member_id: int):
        try:
            with open(cls.created_teams_file, 'r+', encoding='utf-8') as file:
                data = json.load(file)

                for i in range(data['total_teams']):
                    if data['teams'][i]['team_id'] == team_id:
                        team_idx = i
                        break

                for j in range(len(data['teams'][team_idx]['members'])):
                    if data['teams'][team_idx]['members'][j]['ID'] == member_id:
                        member_idx = j
                        break


                members_car_usage = []
                for i in range(3):
                    if i == member_idx:
                        pass
                    else:
                        if i == 2:
                            members_car_usage.append(
                                data['teams'][team_idx]['members'][i]['ARAÇ KULLANABİLİR'] == "Evet" or
                                data['teams'][team_idx]['members'][i]['ARAÇ KULLANABİLİR'] == "E"
                            )
                        else:
                            members_car_usage.append(
                                data['teams'][team_idx]['members'][i]['Araç Kullanımı'] == "Manuel" or
                                data['teams'][team_idx]['members'][i]['Araç Kullanımı'] == "Otomatik"
                            )

                if member_idx == 0:
                    data['teams'][team_idx]['members'][member_idx] = cls.select_member(
                        key='maden_muhendisleri',
                        car_usage=True in members_car_usage
                    )
                elif member_idx == 1:
                    data['teams'][team_idx]['members'][member_idx] = cls.select_member(
                        key='jeoloji_muhendisleri',
                        car_usage=True in members_car_usage
                    )
                elif member_idx == 2:
                    data['teams'][team_idx]['members'][member_idx] = cls.select_member(
                        key='mali_uzmanlari',
                        car_usage=True in members_car_usage
                    )
                else:
                    raise ValueError

                json.dump(data, file, indent=4)

        except (FileNotFoundError, json.JSONDecodeError):
            return {}, {}, 0


    @classmethod
    def assign_teams(cls):
        with open(f"{cls.created_teams_file}", 'r', encoding='utf-8') as file:
            created_teams = dict(json.load(file))

        # Update the assigned teams
        with open("assigned_teams.json", 'r+', encoding='utf-8') as file:
            assigned_teams = dict(json.load(file))
            assigned_teams['total_teams'] += created_teams['total_teams']
            assigned_teams['teams'] += created_teams['teams']

            json.dump(assigned_teams, file, indent=4)

        # Update the member stats
        with open(f"{cls.history_file}", 'r', encoding='utf-8') as file:
            history = json.load(file)

            for team in created_teams['teams']:
                for i, member in enumerate(team['members']):
                    if "ID" in member.keys():
                        for j in range(3):
                            if j != i:
                                if str(team['members'][j]) in history[str(member['ID'])]["team_partner_stats"].keys():
                                    history[str(member['ID'])]["team_partner_stats"][str(team['members'][j])] += 1
                                else:
                                    history[str(member['ID'])]["team_partner_stats"][str(team['members'][j])] = 1

                        history[str(member['ID'])]["team_partner_stats"]
                        history[str(member['ID'])]["worked_teams"].append(team["team_id"])
                        history[str(member['ID'])]["when_available"] = team["end_date"]
                    else:
                        for j in range(3):
                            if j != i:
                                print(member.keys())
                                if str(team['members'][j]) in history[str(member['Sıra No'])]["team_partner_stats"].keys():
                                    history[str(member['Sıra No'])]["team_partner_stats"][str(team['members'][j])] += 1
                                else:
                                    history[str(member['Sıra No'])]["team_partner_stats"][str(team['members'][j])] = 1

                        history[str(member['Sıra No'])]["team_partner_stats"]
                        history[str(member['Sıra No'])]["worked_teams"].append(team["team_id"])
                        history[str(member['Sıra No'])]["when_available"] = team["end_date"]

        with open(f"{cls.created_teams_file}.json", 'w', encoding='utf-8') as file:
            json.dump(
                {
                    "teams": [],
                    "total_teams": 0,
                    "date_created": ""
                }
            )