def init_style():
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

    p {
        color: var(--neutral-dark);
        line-height: 1.5;
    }

    .text-muted {
        color: var(--neutral-medium) !important;
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

    .card-header h4 {
        color: var(--white);
        margin: 0;
    }

    .card-body {
        padding: 20px;
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

    /* Section headers */
    .section-header {
        color: var(--secondary);
        font-weight: 600;
        margin-top: 30px;
        margin-bottom: 15px;
        padding-bottom: 5px;
        border-bottom: 2px solid var(--secondary);
    }

    /* Table Styles */
    .dash-table-container {
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 2px 4px var(--shadow-color);
    }

    .dash-header {
        background-color: var(--secondary) !important;
        color: var(--white) !important;
        font-weight: 600 !important;
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

    /* Filter panel styling */
    .filter-panel {
        background-color: var(--card-bg);
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 4px 8px var(--shadow-color);
    }

    /* Dropdown styling */
    .Select-control {
        border-radius: 6px !important;
        border: 1px solid var(--border-color) !important;
    }

    .Select-control:hover {
        border-color: var(--primary-light) !important;
    }

    .is-focused:not(.is-open) > .Select-control {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 0.2rem rgba(111, 66, 193, 0.25) !important;
    }

    .Select-menu-outer {
        border-radius: 0 0 6px 6px !important;
        border: 1px solid var(--border-color) !important;
        box-shadow: 0 2px 4px var(--shadow-color) !important;
    }

    /* Multi-select dropdown styling */
    .Select--multi .Select-value {
        background-color: var(--primary-light) !important;
        border-color: var(--primary) !important;
        color: white !important;
        border-radius: 4px !important;
        margin-top: 3px !important;
        margin-bottom: 3px !important;
    }

    .Select--multi .Select-value-icon {
        border-right-color: var(--primary) !important;
    }

    .Select--multi .Select-value-icon:hover {
        background-color: var(--primary) !important;
        color: white !important;
    }

    .Select-multi-value-wrapper {
        display: flex !important;
        flex-wrap: wrap !important;
        padding: 2px !important;
    }

    /* Date picker styling */
    .DateInput_input {
        border-radius: 4px !important;
        font-size: 0.9rem !important;
        color: var(--neutral-dark) !important;
    }

    .DateRangePickerInput {
        border-radius: 6px !important;
        border: 1px solid var(--border-color) !important;
    }

    .CalendarDay__selected,
    .CalendarDay__selected:hover {
        background: var(--primary) !important;
        border: 1px double var(--primary) !important;
    }

    .CalendarDay__selected_span {
        background: var(--primary-light) !important;
        border: 1px double var(--primary-light) !important;
        color: var(--white) !important;
    }

    /* Fix for date picker overlapping issues */
    .DayPicker {
        z-index: 1500 !important;
        background-color: white !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2) !important;
    }

    .DayPicker_focusRegion,
    .DayPicker_focusRegion_1 {
        background-color: white !important;
        z-index: 1500 !important;
    }

    .CalendarMonth {
        background-color: white !important;
    }

    .DayPicker_transitionContainer {
        background-color: white !important;
    }

    .DayPickerNavigation {
        z-index: 1501 !important;
    }

    .DayPicker_portal {
        z-index: 1502 !important;
        background-color: rgba(255, 255, 255, 0.95) !important;
    }

    /* Additional fixes for date picker */
    .CalendarMonthGrid {
        background-color: white !important;
    }

    .DateRangePicker_picker {
        background-color: white !important;
        z-index: 1500 !important;
    }

    .SingleDatePicker_picker {
        background-color: white !important;
        z-index: 1500 !important;
    }

    .CalendarMonth_table {
        background-color: white !important;
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

    /* Loading Spinner Styles */
    .dash-spinner.dash-default-spinner {
        opacity: 0.7;
        width: 45px !important;
        height: 45px !important;
        border-width: 5px !important;
        border-color: var(--primary) !important;
        border-bottom-color: transparent !important;
        border-radius: 50% !important;
    }

    .dash-spinner.dash-circle-spinner {
        opacity: 0.7;
        width: 45px !important;
        height: 45px !important;
        border-width: 5px !important;
        border-color: var(--primary) !important;
        border-bottom-color: transparent !important;
        border-radius: 50% !important;
    }

    .dash-spinner-container {
        background-color: rgba(255, 255, 255, 0.8) !important;
    }

    /* Fullscreen loading overlay */
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

    ._dash-loading::before {
        content: '';
        display: block;
        width: 80px;
        height: 80px;
        border-radius: 50%;
        border: 6px solid var(--primary);
        border-color: var(--primary) transparent var(--primary) transparent;
        animation: dash-spinner 1.2s linear infinite;
    }

    @keyframes dash-spinner {
        0% {
            transform: rotate(0deg);
        }
        100% {
            transform: rotate(360deg);
        }
    }
    '''
    return custom_css