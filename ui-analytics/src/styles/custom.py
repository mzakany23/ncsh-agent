"""
Custom CSS styles for the NC Soccer Analytics Dashboard.
"""

custom_css = '''
:root {
    /* Primary Color Palette */
    --primary: #6F42C1;         /* Main brand purple */
    --primary-light: #9A7AD1;   /* Lighter purple for hover states */
    --primary-dark: #5A32A3;    /* Darker purple for active states */

    /* Secondary Colors */
    --secondary: #5B6AFE;       /* Complementary blue for accents */
    --accent: #00C2CB;          /* Teal accent for highlights */

    /* Neutral Colors */
    --neutral-dark: #343A40;    /* Dark gray for text */
    --neutral-medium: #6C757D;  /* Medium gray for secondary text */
    --neutral-light: #E9ECEF;   /* Light gray for backgrounds */
    --white: #FFFFFF;           /* White for cards and contrast */

    /* Semantic Colors */
    --success: #28A745;         /* Green for positive metrics */
    --warning: #5B6AFE;         /* Blue for neutral metrics */
    --danger: #DC3545;          /* Red for negative metrics */

    /* UI Colors */
    --card-bg: var(--white);
    --body-bg: #F8F9FA;
    --border-color: #DEE2E6;
    --shadow-color: rgba(0, 0, 0, 0.05);
}

body {
    font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background-color: var(--body-bg);
    color: var(--neutral-dark);
}

/* Typography */
h1, h2, h3, h4, h5, h6 {
    font-weight: 600;
    color: var(--primary);
}

/* Card Styles */
.card {
    border-radius: 8px;
    box-shadow: 0 4px 8px var(--shadow-color);
    border: none;
    margin-bottom: 20px;
    background-color: var(--card-bg);
    overflow: hidden;
}

.card-header {
    background-color: var(--primary);
    color: var(--white);
    border-bottom: none;
    font-weight: 500;
    padding: 12px 15px;
}

/* Summary Cards */
.summary-card {
    text-align: center;
}

.summary-card .card-header {
    background-color: var(--secondary);
}

.summary-value {
    font-size: 2.2rem;
    font-weight: 700;
    color: var(--primary);
    margin: 10px 0;
}

/* Loading Spinner Styles */
._dash-loading {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(255, 255, 255, 0.85);
    z-index: 9999;
    display: flex;
    justify-content: center;
    align-items: center;
}

._dash-loading-callback::after {
    content: 'Loading dashboard...';
    font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    font-size: 1.5rem;
    color: var(--primary);
    margin-top: 1rem;
    margin-left: -1rem;
}

/* Results styling */
.result-win {
    background-color: rgba(40, 167, 69, 0.1) !important;
    border-left: 3px solid var(--success) !important;
}

.result-draw {
    background-color: rgba(91, 106, 254, 0.1) !important;
    border-left: 3px solid var(--warning) !important;
}

.result-loss {
    background-color: rgba(220, 53, 69, 0.1) !important;
    border-left: 3px solid var(--danger) !important;
}

/* Responsive Design */
@media (max-width: 768px) {
    .summary-card {
        margin-bottom: 15px;
    }

    .section-header {
        margin-top: 20px;
        margin-bottom: 10px;
    }

    .summary-value {
        font-size: 1.8rem;
    }
}
'''