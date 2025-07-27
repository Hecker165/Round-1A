# PDF Outline Extractor - Adobe Hackathon

This project is a submission for Round 1A of the "Connecting the Dots" Adobe Hackathon. It contains a Python script packaged in a Docker container that automatically extracts a structured outline (Title, H1, H2, H3) from PDF documents.

## Approach

The solution uses a hybrid heuristic model to analyze and interpret the structure of PDF documents without relying on large machine learning models. The core approach is a multi-pass pipeline designed to be robust across different document layouts.

1.  **PDF Parsing**: The script reads the input PDF using the `PyMuPDF` library, extracting all text lines along with their properties, such as font size, font name, boldness, and position on the page.

2.  **Base Style Identification**: It first determines the most common style for body text (e.g., 12pt, Times New Roman). This baseline is crucial for differentiating standard text from stylistically distinct headings.

3.  **Candidate Selection**: The script identifies potential heading candidates by finding lines that stand out from the base style. A line is considered a candidate if it has a larger font size, is bold, and has sufficient whitespace above it.

4.  **Heuristic Filtering**: A custom filtering function (`is_valid_candidate`) is applied to remove common false positives. This function uses pattern matching to discard text that is likely a form label, a figure caption, or other non-heading elements.

5.  **Hierarchy Assignment**: To assign heading levels (H1, H2, H3), the script uses a ranking system.
    * It first identifies high-confidence "anchor" headings from numbered sections (e.g., "1.1 Introduction" is an H2).
    * It learns the styles associated with these anchor headings.
    * It then propagates these learned styles to other candidates and ranks any remaining styles based on a "power score" that considers both font size and boldness. This creates a more accurate hierarchy than relying on font size alone.

6.  **Title Detection**: The document title is identified using a scoring system that prioritizes text on the first page with a large font size that is horizontally centered.

## Models and Libraries Used

* **PyMuPDF (fitz)**: The core library used for robust and efficient parsing of PDF files.
* **No ML Models**: The final version of this solution does not use any pre-trained machine learning models. The logic is purely based on layout and text analysis to ensure the solution is lightweight, fast, and fully compliant with the offline and size constraints of the challenge.

## How to Build and Run

The solution is designed to be built and run using Docker, as per the hackathon specifications.

### Build the Docker Image
Navigate to the root of the project directory in your terminal and run the following command:

```bash
docker build --platform linux/amd64 -t mysolutionname:somerandomidentifier .
```

### Run the Container
After the image is built successfully, use the following command to run the container. Make sure you have a folder named input in your project directory containing the PDFs you want to process.

```
docker run --rm -v "$(pwd)/input:/app/input" -v "$(pwd)/output:/app/output" --network none mysolutionname:somerandomidentifier
```

The container will automatically process all .pdf files from the input directory and place the corresponding .json outline files in an output directory within your project folder.
