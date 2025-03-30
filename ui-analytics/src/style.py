def init_style():
    custom_css = '''
    :root {
        /* Apache Superset Color Palette */
        --primary: #20A7C9;         /* Superset blue */
        --primary-light: #66C2DA;   /* Lighter blue for hover states */
        --primary-dark: #1A85A0;    /* Darker blue for active states */

        /* Secondary Colors */
        --secondary: #484848;       /* Dark gray for headers and accents */
        --accent: #FF7F44;          /* Superset orange for highlights */

        /* Neutral Colors */
        --neutral-dark: #323232;    /* Dark gray for text */
        --neutral-medium: #666666;  /* Medium gray for secondary text */
        --neutral-light: #F5F5F5;   /* Light gray for backgrounds */
        --white: #FFFFFF;           /* White for cards and contrast */

        /* Semantic Colors */
        --success: #44B78B;         /* Green for positive metrics */
        --warning: #FCC700;         /* Yellow for neutral metrics */
        --danger: #E04355;          /* Red for negative metrics */

        /* UI Colors */
        --card-bg: var(--white);
        --body-bg: #F8F9FA;
        --border-color: #E0E0E0;
        --shadow-color: rgba(0, 0, 0, 0.05);
    }

    body {
        font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif;
        background-color: var(--body-bg);
        color: var(--neutral-dark);
        font-size: 14px;
    }

    /* Typography */
    h1, h2, h3, h4, h5, h6 {
        font-weight: 600;
        color: var(--secondary);
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
        border-radius: 4px;
        box-shadow: 0 2px 6px var(--shadow-color);
        border: 1px solid var(--border-color);
        margin-bottom: 16px;
        background-color: var(--card-bg);
        overflow: hidden;
    }

    .card-header {
        background-color: var(--white);
        color: var(--secondary);
        font-weight: 600;
        padding: 12px 16px;
        border-bottom: 1px solid var(--border-color);
        font-size: 16px;
    }

    .card-header h4 {
        color: var(--secondary);
        margin: 0;
        font-size: 16px;
    }

    .card-body {
        padding: 16px;
    }

    /* Summary Cards */
    .summary-card {
        text-align: center;
    }

    .summary-card .card-header {
        background-color: var(--white);
        color: var(--secondary);
        border-bottom: 1px solid var(--border-color);
    }

    .summary-value {
        font-size: 2rem;
        font-weight: 700;
        color: var(--primary);
        margin: 10px 0;
    }

    /* Section headers */
    .section-header {
        color: var(--secondary);
        font-weight: 600;
        margin-top: 24px;
        margin-bottom: 12px;
        padding-bottom: 4px;
        border-bottom: 1px solid var(--border-color);
    }

    /* Table Styles */
    .dash-table-container {
        border-radius: 4px;
        overflow: hidden;
        box-shadow: 0 1px 3px var(--shadow-color);
    }

    .dash-header {
        background-color: var(--neutral-light) !important;
        color: var(--secondary) !important;
        font-weight: 600 !important;
        border-bottom: 1px solid var(--border-color) !important;
    }

    /* Results styling */
    .result-win {
        background-color: rgba(68, 183, 139, 0.1) !important;
        border-left: 3px solid var(--success) !important;
    }

    .result-draw {
        background-color: rgba(252, 199, 0, 0.1) !important;
        border-left: 3px solid var(--warning) !important;
    }

    .result-loss {
        background-color: rgba(224, 67, 85, 0.1) !important;
        border-left: 3px solid var(--danger) !important;
    }

    /* Filter panel styling */
    .filter-panel {
        background-color: var(--card-bg);
        border-radius: 4px;
        padding: 16px;
        box-shadow: 0 1px 3px var(--shadow-color);
        border: 1px solid var(--border-color);
    }

    /* Dropdown styling */
    .Select-control {
        border-radius: 4px !important;
        border: 1px solid var(--border-color) !important;
        font-size: 14px !important;
        height: 36px !important;
    }

    .Select-control:hover {
        border-color: var(--primary-light) !important;
    }

    .is-focused:not(.is-open) > .Select-control {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 0.2rem rgba(32, 167, 201, 0.25) !important;
    }

    .Select-menu-outer {
        border-radius: 0 0 4px 4px !important;
        border: 1px solid var(--border-color) !important;
        box-shadow: 0 2px 4px var(--shadow-color) !important;
        font-size: 14px !important;
    }

    /* Multi-select dropdown styling */
    .Select--multi .Select-value {
        background-color: var(--primary-light) !important;
        border-color: var(--primary) !important;
        color: white !important;
        border-radius: 2px !important;
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
        font-size: 14px !important;
        color: var(--neutral-dark) !important;
        height: 36px !important;
    }

    .DateRangePickerInput {
        border-radius: 4px !important;
        border: 1px solid var(--border-color) !important;
        height: 36px !important;
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

    /* Button styling */
    .btn {
        border-radius: 4px;
        font-weight: 500;
        padding: 6px 12px;
        font-size: 14px;
    }

    .btn-primary {
        background-color: var(--primary);
        border-color: var(--primary);
    }

    .btn-primary:hover {
        background-color: var(--primary-dark);
        border-color: var(--primary-dark);
    }

    /* Chart container styling like Superset */
    .chart-container {
        padding: 0;
        border-radius: 4px;
        overflow: hidden;
        background-color: var(--white);
        border: 1px solid var(--border-color);
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
        font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif;
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