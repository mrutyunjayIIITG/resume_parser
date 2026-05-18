import re

def rewrite_parser():
    with open('app/parser.py', 'r', encoding='utf-8') as f:
        content = f.read()

    new_parse_logic = """
        # 8. Refine Experience & Extract Temporal Dates
        experience_detailed = []
        for sec_name in ["experience"]:
            sec_text = sections[sec_name]
            if not sec_text: continue
            
            exp_lines = [l.strip() for l in sec_text.split('\\n') if len(l.strip()) > 5]
            current_role = None
            current_company = None
            
            for line in exp_lines:
                # 8a. Detect Roles
                role_match = re.search(r"\\b(manager|engineer|consultant|analyst|developer|lead|assistant|executive|specialist|officer|coordinator|head|director|intern|trainee|recruiter|generalist)\\b", line, re.I)
                if role_match and len(line.split()) < 10 and not line.startswith(('●', '•', '-', '*')):
                    extracted_roles.append(line)
                    current_role = line
                
                # 8b. Detect Dates
                date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\\s*\\d{2,4}\\s*[-–to]+\\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Present|Current)[a-z]*\\s*\\d{0,4}', line, re.I)
                if not date_match:
                    # Try YYYY - YYYY
                    date_match = re.search(r'\\b(19|20)\\d{2}\\s*[-–to]+\\s*(19|20)\\d{2}|Present\\b', line, re.I)

                if current_role and date_match:
                    date_str = date_match.group(0)
                    start_date = date_str.split('-')[0].strip() if '-' in date_str else date_str
                    end_date = date_str.split('-')[1].strip() if '-' in date_str else "Present"
                    experience_detailed.append({
                        "role": current_role,
                        "company": "Unknown", # Needs DB normalizer to accurately guess
                        "start_date": start_date,
                        "end_date": end_date,
                        "is_current": "present" in end_date.lower() or "current" in end_date.lower()
                    })
                    current_role = None # reset to avoid duplicate attachment

        # 9. Smart Company Filtering (using Normalizer)
        valid_companies = []
        for comp in extracted_companies:
            comp_id, comp_canon = normalizer.normalize_company(comp)
            if comp_id: # Only trust it if it actually exists in our master dictionary!
                valid_companies.append({"id": comp_id, "raw": comp, "canonical": comp_canon})

        # 10. Smart Project Grouping
        projects_detailed = []
        current_proj = None
        for line in sections["projects"].split('\\n'):
            line = line.strip()
            if not line: continue
            if line.isupper() and len(line) > 5 and len(line.split()) < 8:
                if current_proj: projects_detailed.append(current_proj)
                current_proj = {"title": line, "description": []}
            elif current_proj and line.startswith(('•', '-', '*', '●')):
                current_proj["description"].append(line)
            elif not current_proj and len(line) > 10:
                current_proj = {"title": "Project", "description": [line]}
        if current_proj: projects_detailed.append(current_proj)

        # Final Structured Result
        initial_result = {
            "candidate_name": name or "Unknown",
            "contact": {
                "emails": emails,
                "phones": phones
            },
            "experience": {
                "detected_roles": sorted(list(set([r.strip() for r in extracted_roles if len(r.strip()) > 3])))[:10]
            },
            "experience_detailed": experience_detailed,
            "education": {
                "institutes_and_degrees": sorted(list(set([e.strip() for e in (extracted_degrees + extracted_institutes) if len(e.strip()) > 3])))[:10]
            },
            "skills": sorted(list(set([s.strip().title() for s in extracted_skills if len(s.strip()) > 1]))),
            "certifications": sorted(list(set([c.strip() for c in sections["certifications"].split('\\n') if len(c.strip()) > 5]))),
            "projects": [f"{p['title']}: {' '.join(p['description'])}" for p in projects_detailed] if projects_detailed else [p.strip() for p in sections["projects"].split('\\n') if len(p.strip()) > 10],
            "word_count": len(text.split())
        }

        # Local Junk Filter (Post-AI Cleanup)
        junk_skills = {"Only", "Player", "Thoroughly", "Concept", "Made", "Learned", "This", "Using", "Power", "Features", "Showcases", "Working", "Design", "Visually", "Format", "Searchforfoodrecipes", "The", "Thoroughly", "Learned Frontend Web Development Thoroughly"}
        if "skills" in initial_result:
            clean_list = []
            for s in initial_result["skills"]:
                if s in junk_skills: continue
                if len(s) > 40 or len(s.split()) > 4: continue
                clean_list.append(s)
            
            normalized_skills = normalizer.process_list(clean_list)
            initial_result["skills"] = normalized_skills
            # Map years of experience to skills using a simple heuristic since AI isn't here
            years = 2 if len(experience_detailed) > 0 else 0
            initial_result["skills_detailed"] = [{"name": s, "years_of_experience": years} for s in normalized_skills]

        # Optional LLM Refinement (Skipped if key is missing)
        refined_result = refiner.refine(initial_result, text)
        
        # ATS Normalization Post-Processing
        ats_data = {
            "location": {"id": None, "raw": None},
            "designations": [],
            "companies": valid_companies,
            "degrees": []
        }
        
        for loc in extracted_locations:
            if len(loc) > 30: continue
            loc_id, loc_canon = normalizer.normalize_location(loc)
            if loc_id:
                ats_data["location"] = {"id": loc_id, "raw": loc, "canonical": loc_canon}
                break
        if not ats_data["location"]["id"] and extracted_locations:
            ats_data["location"]["raw"] = extracted_locations[0]
            
        roles_to_check = list(set(extracted_roles))
        if "experience" in refined_result and isinstance(refined_result["experience"], list):
            roles_to_check.extend([str(r) for r in refined_result["experience"] if isinstance(r, str)])
        roles_to_check = list(set(roles_to_check))
        
        for role in roles_to_check:
            desig_id, desig_canon = normalizer.normalize_designation(role)
            ats_data["designations"].append({"id": desig_id, "raw": role, "canonical": desig_canon})
                
        degs_to_check = list(set(extracted_degrees))
        if "education" in refined_result and isinstance(refined_result["education"], list):
             degs_to_check.extend([str(d) for d in refined_result["education"] if isinstance(d, str)])
        degs_to_check = list(set(degs_to_check))
        
        for deg in degs_to_check:
            deg_id, deg_canon = normalizer.normalize_degree(deg)
            ats_data["degrees"].append({"id": deg_id, "raw": deg, "canonical": deg_canon})
                
        refined_result["ats_normalized"] = ats_data
        
        return refined_result"""

    start_marker = "# 8. Refine Experience"
    end_marker = "return refined_result"
    
    if start_marker in content and end_marker in content:
        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker) + len(end_marker)
        
        new_content = content[:start_idx] + new_parse_logic.strip() + content[end_idx:]
        with open('app/parser.py', 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Successfully updated app/parser.py")
    else:
        print("Failed to find replacement target in app/parser.py")

if __name__ == "__main__":
    rewrite_parser()
