# AI-Powered Alcohol Label Verification App

Requirements and Constraints

*Extracted from discovery interviews and the technical requirements document. Background that doesn't affect the build has been left out.*

## What the app does

It compares the details on an alcohol label image against the details entered in the label application, and flags any mismatches.

## Functional requirements

### Core verification
- **FR-1:** Accept a label image and the application data it should match, which is the expected value for each field.
- **FR-2:** Read the text on the label image using OCR or AI vision.
- **FR-3:** Check each label field against its application value and show a pass or fail for each one:
  - Brand name
  - Class/type (for example, "Kentucky Straight Bourbon Whiskey")
  - Alcohol content (for example, "45% Alc./Vol. (90 Proof)"; some wines and beers don't need it)
  - Net contents (for example, "750 mL")
  - Name and address of the bottler or producer
  - Country of origin (imports only)
  - Government Health Warning (required on every alcohol label)
- **FR-4: Fuzzy matching for ordinary fields.** Small formatting differences should not count as failures. For example, "STONE'S THROW" and "Stone's Throw" are the same name. Ideally the app shows three results: match, likely match (needs review), or mismatch, so the agent still makes the final call.
- **FR-5: Strict matching for the Government Warning:**
  - The wording must match the standard statement word for word.
  - "GOVERNMENT WARNING:" must be in all caps. Title case ("Government Warning") is a rejection.
  - "GOVERNMENT WARNING:" must be bold.
  - Ideally, flag warnings that look deliberately hidden, such as very small or tucked-away text.
- **FR-6:** Show clear results for each field, with the expected value next to what was found and the reason for any failure.

### Batch processing
- **FR-7:** Allow batch uploads. Importers sometimes submit 200–300 applications at once, so the app should handle many label and application pairs in one go and show a summary of the results.

### Image handling (nice to have)
- **FR-8:** Cope with imperfect photos taken at an angle, in poor lighting, or with glare. If a label can't be read, say so clearly instead of guessing.

## Non-functional requirements

| **Area**           | **Requirement**                                                                                                                                                                                                                                     |
|--------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Speed**          | Each label must come back in **about 5 seconds or less**. This is the main reason the last vendor pilot failed: it took 30–40 seconds, and agents went back to checking by eye.                                                                     |
| **Usability**      | It has to work for users who aren't comfortable with technology. Half the team is over 50, and the benchmark is "a 73-year-old could figure it out." Use a clean, obvious layout, large clear controls, and no hidden menus or buttons to hunt for. |
| **Workflow fit**   | It should make agents faster, not add steps. It supports their judgment rather than replacing it.                                                                                                                                                   |
| **Error handling** | Give clear messages for bad uploads, unreadable images, missing fields and timeouts. This is one of the evaluation criteria.                                                                                                                        |
| **Reliability**    | Results have to be accurate enough that agents trust them. If they don't, they'll stop using it.                                                                                                                                                    |
| **Code quality**   | Well organized and maintainable. Choose technology that fits a prototype, not an enterprise system.                                                                                                                                                 |

## Constraints
- **Standalone prototype.** Don't integrate with COLA.
- **Restricted network.** The agency firewall blocks outbound traffic to many domains, and it broke the last vendor's ML features. Prefer OCR or models that run locally or on your own server. If you use a cloud AI API, plan a fallback or make the design work without it.
- **Azure environment.** Their infrastructure runs on Azure and the existing systems use .NET. You can use any stack, but these fit their environment if you ever move toward production.
- **No sensitive data storage.** Don't keep PII or anything sensitive. Processing images without storing them is safest.
- **Rules depend on beverage type.** Requirements differ for beer, wine and distilled spirits. For example, alcohol content is optional for some wines and beers, and country of origin applies only to imports.
- **Deliverables:**
  - A source code repository with a README covering setup and run steps, your approach, the tools you used and your assumptions
  - A deployed URL they can open and test
- **Test data is up to you.** Create or source your own test labels. AI image generators are suggested.

## Evaluation criteria

Your work will be judged on:
- Correctness and completeness of the core requirements
- Code quality
- Whether your technical choices suit the scope
- User experience and error handling
- How closely you followed the requirements
- Creative problem-solving

## Things the document leaves open

Settle these yourself and record them in the README as assumptions:
- **Where the application data comes from.** Since there's no COLA link, it is probably a form the user fills in, or a CSV/JSON file for batches.
- **Exact warning wording.** The document only says "[Standard government warning text]". The legal wording is in 27 CFR Part 16: *"GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems."* Check it against ttb.gov before you hard-code it.
- **Checking for bold text.** OCR alone usually can't tell whether text is bold. You'll probably need a vision model or an image-analysis heuristic.
- **Speed vs. local processing.** The 5-second target together with the firewall limits pushes you toward a fast local OCR engine. A cloud vision model could serve as an optional upgrade.
