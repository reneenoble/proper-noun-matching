import csv
from rapidfuzz import fuzz, process

def find_best_match_rapidfuzz(query: str, names_options: list[str]) -> tuple[str, float]:
    """Uppercase wrapper for rapidfuzz."""
    query_upper = query.upper()
    names_upper = [name.upper() for name in names_options]

    # Use rapid fuzz to find the registered name that has the best match score
    match, score, idx = process.extractOne(query_upper, names_upper, scorer=fuzz.WRatio)
    if match:   
        original_idx = names_upper.index(match)
        return names_options[original_idx], score
    return ("NO MATCH", 0)


def find_best_match_rapidfuzz_split_name(query: list[str], names_options: list[list[str]]) -> tuple[str, float]:
    """Find the best match for any part of a split name."""
    for name_parts in names_options:
        best_match = ("NO MATCH", 0)
        for part in query:
            match, score = find_best_match_rapidfuzz(part, name_parts)
        if score > best_match[1]:
            best_match = (name_parts, score)
    return best_match

def get_attendee_name_components(student: dict) -> list[str]:
    """Get the components of a name for matching."""
    name_parts = student["Student's full name"].split()
    buyer_last_name = student["Last name"] # this is of the ticket purchaser, could be the student, a parent (potential shared last name), or non-matching last name.
    name_parts.append(buyer_last_name)
    return name_parts

def get_attendee_index_by_name(name: str, student_list: list[dict]) -> int | None:
    """Get the index of an attendee by their full name."""
    for i, student in enumerate(student_list):
        if student["Student's full name"] == name:
            return i
    return None


def read_rego_data(rego_data):
    with open(rego_data, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        rego_attendees = [row for row in reader]
        checked_in_students = [row for row in rego_attendees if row.get("Checked in") == "Checked in"]
        not_checked_in_students = [row for row in rego_attendees if row.get("Checked in") != "Checked in"]
    return checked_in_students, not_checked_in_students


def read_survey_data(survey_data):
    with open(survey_data, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        survey_responses = [row for row in reader]
    return survey_responses




def read_workshop_data(rego_file, survey_file):
    checked_in_students, not_checked_in_students = read_rego_data(rego_file)
    survey_responses = read_survey_data(survey_file)
    return checked_in_students, not_checked_in_students, survey_responses


# Extract data from the REAL_DATA attendee-report csv file
rego_data = "REAL_data/attendee-report-2025-T3.csv"

# Extra data from the REAL_DATA start of day survey file
survey_data = "REAL_data/GPN Sydney 2025 – 3 Start of Day.csv"

checked_in_students, not_checked_in_students, survey_responses = read_workshop_data(rego_data, survey_data)
print(f"len(checked_in_students): {len(checked_in_students)}, len(not_checked_in_students): {len(not_checked_in_students)}")
print(f"len(survey_responses): {len(survey_responses)}")

def basic_fuzzy_match(checked_in_students, not_checked_in_students, survey_responses):
    
    checked_in_names = [student["Student's full name"] for student in checked_in_students]
    not_checked_in_names = [student["Student's full name"] for student in not_checked_in_students]

    bad_matches = []
    good_matches = []

    matched_surveyed_students = []
    unmatched_surveyed_students = []
    matched_checked_in_students = []
    unmatched_checked_in_students = checked_in_students.copy()
    matched_not_checked_in_attendees = []

    # For each student in the start of day survey, find their corresponding registration details
    for student in survey_responses:
        student_fullname = student["Full name to display on certificate"]
        print(student_fullname)
        best_match, score = find_best_match_rapidfuzz(student_fullname, checked_in_names)
        print(best_match, score)

        best_match_not_checked_in, score_not_checked_in = find_best_match_rapidfuzz(student_fullname, not_checked_in_names)
        print(best_match_not_checked_in, score_not_checked_in)
        print()

        if score < 80 and score_not_checked_in < 80:
            bad_matches.append((student_fullname, best_match, score, best_match_not_checked_in, score_not_checked_in))
            unmatched_surveyed_students.append(student)
        else:
            good_matches.append((student_fullname, best_match, score, best_match_not_checked_in, score_not_checked_in))
            matched_surveyed_students.append(student)
            if score > score_not_checked_in:
                # This means the best match is a checked-in student
                # Remove the matched checked-in student from the unmatched list
                unmatched_checked_in_students.pop(get_attendee_index_by_name(best_match, unmatched_checked_in_students))
            else:
                matched_not_checked_in_attendees.append(student)
                not_checked_in_students.pop(get_attendee_index_by_name(best_match_not_checked_in, not_checked_in_students))




    for student_fullname, best_match, score, best_match_not_checked_in, score_not_checked_in in bad_matches:
        print(f"Bad match for '{student_fullname}':")
        print(f"  Best checked-in match: '{best_match}' with score {score}")
        print(f"  Best not checked-in match: '{best_match_not_checked_in}' with score {score_not_checked_in}")
        print()

    print(f"Average score for good matches: {sum(score for _, _, score, _, _ in good_matches) / len(good_matches) if good_matches else 0}")

    print(f"Total good matches: {len(good_matches)}")
    print(f"Average score for good matches: {sum(score for _, _, score, _, _ in good_matches) / len(good_matches) if good_matches else 0}")

    print(f"Total bad matches: {len(bad_matches)}")
    print(f"Average score for bad matches: {sum(score for _, _, score, _, _ in bad_matches) / len(bad_matches) if bad_matches else 0}")

    unmatched_checked_in_students = [student for student in checked_in_students if student not in matched_checked_in_students]
    return good_matches, bad_matches, unmatched_surveyed_students, unmatched_checked_in_students


def extra_fuzzy_match(checked_in_students, not_checked_in_students, survey_responses):
    # TODO add the code here for the version where we use extra names from the registration data
        pass

def main():
    good_matches, bad_matches, unmatched_surveyed_students, unmatched_checked_in_students = basic_fuzzy_match(checked_in_students, not_checked_in_students, survey_responses)


    # Go through the attendee report, get all the checked in students, and then remove all the students who were found in the matching process
    for student in unmatched_surveyed_students:
        print(f"Unmatched student: {student["Full name to display on certificate"]}")

    # write good and bad matches to csv
    with open("rapid_fuzz_matches.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Student", "Best Match", "Score", "Best Not Checked In Match", "Not Checked In Score", "match category", "top score"])
        for student_fullname, best_match, score, best_match_not_checked_in, score_not_checked_in in good_matches:
            writer.writerow([student_fullname, best_match, score, best_match_not_checked_in, score_not_checked_in, "good match", max(score, score_not_checked_in)])
        for student_fullname, best_match, score, best_match_not_checked_in, score_not_checked_in in bad_matches:
            writer.writerow([student_fullname, best_match, score, best_match_not_checked_in, score_not_checked_in, "bad match", max(score, score_not_checked_in)])

if __name__ == "__main__":
    main()


