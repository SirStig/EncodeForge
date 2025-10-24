# EncodeForge UI Overhaul - Comprehensive Implementation Plan

**Project Goal**: Transform EncodeForge into a polished, responsive desktop application with Apple/macOS-inspired aesthetics, proper responsive design, theming support, and professional depth.

---

## Table of Contents
1. [Current State Analysis](#1-current-state-analysis)
2. [Responsive Design System](#2-responsive-design-system)
3. [Theme System Architecture](#3-theme-system-architecture)
4. [Splash Screen Enhancement](#4-splash-screen-enhancement)
5. [Sidebar Redesign](#5-sidebar-redesign)
6. [Settings Integration](#6-settings-integration)
7. [Table Improvements](#7-table-improvements)
8. [Depth & Animation](#8-depth--animation)
9. [Component Fixes](#9-component-fixes)
10. [FXML Modifications](#10-fxml-modifications)
11. [Java Code Changes](#11-java-code-changes)
12. [Testing Strategy](#12-testing-strategy)

---

## 1. Current State Analysis

### Issues Identified

#### 1.1 Responsive Design Problems
- **Hardcoded pixel values**: All font sizes, padding, margins use `px` instead of relative units
- **No media queries**: CSS doesn't adapt to different screen resolutions
- **Fixed minimum sizes**: MIN_WIDTH=1000px, MIN_HEIGHT=700px doesn't scale
- **UI breaks on smaller screens**: Components overflow viewport on screens < 1080p
- **No viewport-based sizing**: Nothing uses `vw`, `vh`, or percentage units

#### 1.2 Component Sizing Issues
- **Sidebar**: Fixed width (80-100px) too small for horizontal icon+text layout
- **Mode buttons**: Vertical layout (icon over text) wastes space, icons too large (22px)
- **Buttons**: Inconsistent sizing across toolbar (26-30px height) vs main buttons
- **Text fields**: Fixed 36px height doesn't scale with screen size
- **ComboBoxes**: Multiple sizes (28px, 32px) without clear rationale
- **Tables**: Columns don't auto-fill width, leave empty space

#### 1.3 Typography Problems
- **Inconsistent font sizes**: 10-22px range with no systematic scale
- **Poor hierarchy**: Similar sizes for different importance levels
- **Fixed line heights**: No relative spacing for readability
- **No font size scaling**: Same sizes on all screen resolutions

#### 1.4 Spacing & Layout Issues
- **Inconsistent spacing**: Padding/margin values (4-20px) lack system
- **No spacing scale**: Random values instead of 4/8px base unit
- **Cramped layouts**: Insufficient breathing room between elements
- **No grid system**: Layout inconsistencies across different sections

#### 1.5 Depth & Visual Design
- **Flat appearance**: Shadows underutilized or inconsistent
- **Missing hover states**: Limited interactive feedback
- **No transitions**: Instant state changes feel jarring
- **Minimal gradients**: Lost opportunity for depth perception
- **Poor visual hierarchy**: Similar styling for all importance levels

#### 1.6 Specific Component Issues
- **Spinner text cutoff**: Internal padding causes number truncation
- **Table columns**: Don't auto-resize to fill available space
- **No order numbers**: Queue tables lack position indicators
- **Menu bar unnecessary**: File/Edit/Tools/Help could be consolidated
- **Settings as dialog**: Should be integrated mode view instead

---

## 2. Responsive Design System

### 2.1 Base Unit System

```css
/* Root sizing based on screen resolution */
:root {
    /* Base unit for spacing (4px system) */
    --space-unit: 0.25rem; /* 4px at 16px base */
    
    /* Spacing scale (4/8/12/16/20/24/32/40/48/64px) */
    --space-xs: calc(var(--space-unit) * 1);   /* 4px */
    --space-sm: calc(var(--space-unit) * 2);   /* 8px */
    --space-md: calc(var(--space-unit) * 3);   /* 12px */
    --space-lg: calc(var(--space-unit) * 4);   /* 16px */
    --space-xl: calc(var(--space-unit) * 5);   /* 20px */
    --space-2xl: calc(var(--space-unit) * 6);  /* 24px */
    --space-3xl: calc(var(--space-unit) * 8);  /* 32px */
    --space-4xl: calc(var(--space-unit) * 10); /* 40px */
    --space-5xl: calc(var(--space-unit) * 12); /* 48px */
    --space-6xl: calc(var(--space-unit) * 16); /* 64px */
}
```

### 2.2 Screen Resolution Breakpoints

```css
/* Extra Small: 1024-1279px (laptops, small displays) */
@media screen and (max-width: 1279px) {
    :root {
        --base-font-size: 13px;
        --scale-factor: 0.85;
    }
}

/* Small: 1280-1599px (standard 720p/1080p) */
@media screen and (min-width: 1280px) and (max-width: 1599px) {
    :root {
        --base-font-size: 14px;
        --scale-factor: 0.9;
    }
}

/* Medium: 1600-1919px (standard 1080p) */
@media screen and (min-width: 1600px) and (max-width: 1919px) {
    :root {
        --base-font-size: 15px;
        --scale-factor: 1.0;
    }
}

/* Large: 1920-2559px (1080p/1440p) */
@media screen and (min-width: 1920px) and (max-width: 2559px) {
    :root {
        --base-font-size: 16px;
        --scale-factor: 1.1;
    }
}

/* Extra Large: 2560px+ (1440p/4K) */
@media screen and (min-width: 2560px) {
    :root {
        --base-font-size: 18px;
        --scale-factor: 1.25;
    }
}
```

### 2.3 Typography Scale

```css
:root {
    /* Font sizes using rem (relative to root) */
    --font-xs: 0.75rem;      /* 12px at 16px base */
    --font-sm: 0.875rem;     /* 14px */
    --font-base: 1rem;       /* 16px */
    --font-lg: 1.125rem;     /* 18px */
    --font-xl: 1.25rem;      /* 20px */
    --font-2xl: 1.5rem;      /* 24px */
    --font-3xl: 1.875rem;    /* 30px */
    --font-4xl: 2.25rem;     /* 36px */
    
    /* Line heights */
    --leading-tight: 1.25;
    --leading-normal: 1.5;
    --leading-relaxed: 1.75;
    
    /* Font weights */
    --font-normal: 400;
    --font-medium: 500;
    --font-semibold: 600;
    --font-bold: 700;
}
```

### 2.4 Component Sizing Variables

```css
:root {
    /* Button heights */
    --button-sm: calc(2rem * var(--scale-factor));    /* ~32px scaled */
    --button-md: calc(2.25rem * var(--scale-factor)); /* ~36px scaled */
    --button-lg: calc(2.5rem * var(--scale-factor));  /* ~40px scaled */
    
    /* Input heights */
    --input-sm: calc(2rem * var(--scale-factor));
    --input-md: calc(2.5rem * var(--scale-factor));
    --input-lg: calc(3rem * var(--scale-factor));
    
    /* Border radius */
    --radius-sm: 4px;
    --radius-md: 6px;
    --radius-lg: 8px;
    --radius-xl: 12px;
    
    /* Shadow depths */
    --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.2);
    --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.3);
    --shadow-2xl: 0 25px 50px -12px rgba(0, 0, 0, 0.4);
}
```

### 2.5 Minimum Window Sizes (Responsive)

```java
// In MainController.java - Update constants based on screen size
private static final double MIN_WIDTH_RATIO = 0.6;   // 60% of screen width
private static final double MIN_HEIGHT_RATIO = 0.7;  // 70% of screen height
private static final double ABSOLUTE_MIN_WIDTH = 900;  // Down from 1000
private static final double ABSOLUTE_MIN_HEIGHT = 600; // Down from 700

// Calculate minimum based on screen resolution
Rectangle2D screenBounds = Screen.getPrimary().getVisualBounds();
double minWidth = Math.max(screenBounds.getWidth() * MIN_WIDTH_RATIO, ABSOLUTE_MIN_WIDTH);
double minHeight = Math.max(screenBounds.getHeight() * MIN_HEIGHT_RATIO, ABSOLUTE_MIN_HEIGHT);
```

---

## 3. Theme System Architecture

### 3.1 Theme Structure

```
themes/
├── default-dark/
│   ├── theme.json          # Theme metadata
│   ├── colors.css          # Color variables
│   ├── typography.css      # Font settings
│   └── components.css      # Component overrides
├── light-mode/             # Future theme
└── custom-user-theme/      # User-created themes
```

### 3.2 Theme Definition (theme.json)

```json
{
    "name": "Default Dark",
    "version": "1.0.0",
    "author": "EncodeForge",
    "description": "Default dark theme with Apple-inspired aesthetics",
    "baseTheme": "dark",
    "files": [
        "colors.css",
        "typography.css",
        "components.css"
    ],
    "preview": "preview.png"
}
```

### 3.3 Color System (colors.css)

```css
:root {
    /* Base colors */
    --bg-primary: #1c1c1e;
    --bg-secondary: #2c2c2e;
    --bg-tertiary: #3a3a3c;
    --bg-elevated: #252526;
    
    /* Text colors */
    --text-primary: #ffffff;
    --text-secondary: #e5e5e7;
    --text-tertiary: #a0a0a0;
    --text-disabled: #636366;
    
    /* Accent colors */
    --accent-primary: #0a84ff;
    --accent-hover: #3399ff;
    --accent-pressed: #0066cc;
    
    /* Semantic colors */
    --success: #34c759;
    --warning: #ffb900;
    --error: #ff453a;
    --info: #00a8ff;
    
    /* Border colors */
    --border-subtle: rgba(58, 58, 60, 0.3);
    --border-default: rgba(72, 72, 74, 0.6);
    --border-strong: rgba(90, 90, 92, 0.8);
}
```

### 3.4 Theme Loader (Java)

```java
public class ThemeManager {
    private static final Path THEMES_DIR = PathManager.getAppDataDir().resolve("themes");
    private Theme currentTheme;
    
    public void loadTheme(String themeName) throws IOException {
        Path themePath = THEMES_DIR.resolve(themeName);
        Path metadataFile = themePath.resolve("theme.json");
        
        // Validate theme structure
        if (!validateTheme(themePath)) {
            throw new IOException("Invalid theme structure");
        }
        
        // Load theme metadata
        ThemeMetadata metadata = parseThemeMetadata(metadataFile);
        
        // Apply CSS files in order
        Scene scene = primaryStage.getScene();
        scene.getStylesheets().clear();
        scene.getStylesheets().add(getClass().getResource("/styles/base.css").toExternalForm());
        
        for (String cssFile : metadata.getFiles()) {
            Path cssPath = themePath.resolve(cssFile);
            scene.getStylesheets().add(cssPath.toUri().toString());
        }
        
        currentTheme = new Theme(themeName, metadata);
    }
    
    private boolean validateTheme(Path themePath) {
        // Check required files exist
        // Validate CSS syntax
        // Check for malicious content
        return true;
    }
}
```

### 3.5 Theme Settings Integration

Add to Settings dialog:
- Theme selector dropdown
- Theme preview
- Import custom theme (from .zip)
- Export current theme
- Reset to default theme

---

## 4. Splash Screen Enhancement

### 4.1 Enhanced InitializationDialog

**Current State**: Basic dialog with progress bar and status text

**Improvements Needed**:
1. Add EncodeForge logo
2. Show version number
3. Add animated loading indicator
4. Show startup steps clearly
5. Fade in/out animations
6. Center on screen properly

### 4.2 New InitializationDialog.fxml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<?import javafx.geometry.Insets?>
<?import javafx.scene.control.*?>
<?import javafx.scene.layout.*?>
<?import javafx.scene.text.Font?>
<?import javafx.scene.image.ImageView?>
<?import javafx.scene.image.Image?>

<VBox xmlns="http://javafx.com/javafx" xmlns:fx="http://javafx.com/fxml"
      prefWidth="600" prefHeight="450" styleClass="splash-screen" spacing="0">
    
    <!-- Logo Section -->
    <VBox alignment="CENTER" spacing="12" styleClass="splash-header" VBox.vgrow="NEVER">
        <padding>
            <Insets top="40" right="40" bottom="20" left="40"/>
        </padding>
        
        <!-- Logo placeholder - will add actual logo later -->
        <Label text="⚡" styleClass="splash-logo-icon" />
        
        <Label text="EncodeForge" styleClass="splash-title">
            <font>
                <Font name="System Bold" size="32"/>
            </font>
        </Label>
        
        <Label fx:id="versionLabel" text="Version 0.4.0" styleClass="splash-version">
            <font>
                <Font size="13"/>
            </font>
        </Label>
    </VBox>
    
    <!-- Progress Section -->
    <VBox spacing="20" VBox.vgrow="ALWAYS" styleClass="splash-content">
        <padding>
            <Insets top="20" right="40" bottom="30" left="40"/>
        </padding>
        
        <!-- Current Step -->
        <Label fx:id="stageLabel" text="Initializing..." styleClass="splash-stage">
            <font>
                <Font size="14" />
            </font>
        </Label>
        
        <!-- Status Message -->
        <Label fx:id="statusLabel" text="Checking dependencies..." 
               wrapText="true" minHeight="50" styleClass="splash-status">
            <font>
                <Font size="12"/>
            </font>
        </Label>
        
        <!-- Progress Bar -->
        <VBox spacing="8">
            <ProgressBar fx:id="progressBar" progress="0" 
                        prefWidth="Infinity" prefHeight="8" 
                        styleClass="splash-progress-bar"/>
            
            <Label fx:id="progressLabel" text="0%" styleClass="splash-progress-label">
                <font>
                    <Font size="11"/>
                </font>
            </Label>
        </VBox>
        
        <!-- Step Indicators -->
        <HBox spacing="12" alignment="CENTER" styleClass="splash-steps">
            <Label fx:id="step1" text="●" styleClass="step-indicator, step-active"/>
            <Label fx:id="step2" text="●" styleClass="step-indicator"/>
            <Label fx:id="step3" text="●" styleClass="step-indicator"/>
            <Label fx:id="step4" text="●" styleClass="step-indicator"/>
        </HBox>
        
        <!-- Detailed Log (Collapsible) -->
        <TitledPane fx:id="logPane" text="Show Details" 
                    expanded="false" animated="true" 
                    styleClass="splash-log-pane" VBox.vgrow="ALWAYS">
            <ScrollPane fitToWidth="true" fitToHeight="true">
                <TextArea fx:id="logArea" editable="false" wrapText="true" 
                         prefRowCount="8" styleClass="splash-log-area">
                    <font>
                        <Font name="Consolas" size="10"/>
                    </font>
                </TextArea>
            </ScrollPane>
        </TitledPane>
    </VBox>
    
    <!-- Footer -->
    <HBox alignment="CENTER" spacing="10" styleClass="splash-footer">
        <padding>
            <Insets top="15" right="40" bottom="25" left="40"/>
        </padding>
        <Label text="© 2025 EncodeForge" styleClass="splash-copyright"/>
    </HBox>
    
</VBox>
```

### 4.3 Splash Screen Styling

```css
/* Splash Screen Styles */
.splash-screen {
    -fx-background-color: linear-gradient(to bottom, #0a0a0a 0%, #1c1c1e 100%);
    -fx-border-color: rgba(10, 132, 255, 0.3);
    -fx-border-width: 1;
    -fx-border-radius: 12;
    -fx-background-radius: 12;
    -fx-effect: dropshadow(gaussian, rgba(0, 0, 0, 0.8), 40, 0.2, 0, 10);
}

.splash-header {
    -fx-background-color: transparent;
}

.splash-logo-icon {
    -fx-font-size: 64px;
    -fx-text-fill: #0a84ff;
    -fx-effect: dropshadow(gaussian, rgba(10, 132, 255, 0.6), 12, 0, 0, 0);
}

.splash-title {
    -fx-text-fill: #ffffff;
    -fx-font-weight: 700;
    -fx-letter-spacing: 1px;
}

.splash-version {
    -fx-text-fill: #a0a0a0;
}

.splash-content {
    -fx-background-color: transparent;
}

.splash-stage {
    -fx-text-fill: #0a84ff;
    -fx-font-weight: 600;
}

.splash-status {
    -fx-text-fill: #e5e5e7;
}

.splash-progress-bar {
    -fx-background-color: #2c2c2e;
    -fx-background-radius: 4;
}

.splash-progress-bar .bar {
    -fx-background-color: linear-gradient(to right, #0a84ff 0%, #3399ff 100%);
    -fx-background-radius: 4;
    -fx-background-insets: 0;
}

.splash-progress-label {
    -fx-text-fill: #a0a0a0;
    -fx-alignment: center;
}

.splash-steps {
    -fx-padding: 10 0;
}

.step-indicator {
    -fx-font-size: 12px;
    -fx-text-fill: #3a3a3c;
}

.step-indicator.step-active {
    -fx-text-fill: #0a84ff;
    -fx-effect: dropshadow(gaussian, rgba(10, 132, 255, 0.5), 6, 0, 0, 0);
}

.step-indicator.step-completed {
    -fx-text-fill: #34c759;
}

.splash-footer {
    -fx-background-color: transparent;
    -fx-border-color: rgba(58, 58, 60, 0.3) transparent transparent transparent;
    -fx-border-width: 1 0 0 0;
}

.splash-copyright {
    -fx-text-fill: #636366;
    -fx-font-size: 10px;
}
```

### 4.4 Fade Animations (Java)

```java
public class InitializationDialog {
    
    private void showWithFadeIn() {
        FadeTransition fadeIn = new FadeTransition(Duration.millis(300), dialogPane);
        fadeIn.setFromValue(0.0);
        fadeIn.setToValue(1.0);
        fadeIn.play();
    }
    
    public void closeWithFadeOut(Runnable onComplete) {
        FadeTransition fadeOut = new FadeTransition(Duration.millis(200), dialogPane);
        fadeOut.setFromValue(1.0);
        fadeOut.setToValue(0.0);
        fadeOut.setOnFinished(e -> {
            dialog.close();
            if (onComplete != null) onComplete.run();
        });
        fadeOut.play();
    }
    
    public void updateStep(int stepNumber, String label) {
        // Update step indicators
        for (int i = 1; i <= 4; i++) {
            Label step = (Label) dialogPane.lookup("#step" + i);
            if (i < stepNumber) {
                step.getStyleClass().add("step-completed");
                step.getStyleClass().remove("step-active");
            } else if (i == stepNumber) {
                step.getStyleClass().add("step-active");
                step.getStyleClass().remove("step-completed");
            } else {
                step.getStyleClass().removeAll("step-active", "step-completed");
            }
        }
        
        stageLabel.setText(label);
    }
}
```

---

## 5. Sidebar Redesign

### 5.1 Current Sidebar Issues

- Vertical layout wastes space (icon 22px over text)
- Fixed width 80-100px too narrow for horizontal layout
- Icons too large relative to text
- FFmpeg status button cramped
- Settings button separate from modes

### 5.2 New Sidebar Layout

**Dimensions**:
- Width: 140-160px (responsive)
- Button height: 40px (vs current ~60px vertical)
- Icon size: 14px (match text size)
- Spacing: 8px between buttons

**Structure**:
```
┌─────────────────┐
│ ⚡ EncodeForge  │ (app icon + title)
├─────────────────┤
│ MODES           │ (section header)
│ 🎬 Encoder      │ (horizontal: icon + text)
│ 📝 Subtitles    │
│ 📁 Metadata     │
│ ⚙️  Settings    │ (moved here!)
├─────────────────┤
│ FILES           │
│ 📄 Add Files    │
│ 📂 Add Folder   │
├─────────────────┤
│ [FFmpeg Status] │ (card-style)
│ ✓ FFmpeg Found  │
│ Version 6.0     │
└─────────────────┘
```

### 5.3 FXML Changes for Sidebar

```xml
<VBox fx:id="sidebar" styleClass="sidebar" minWidth="140" prefWidth="155" maxWidth="180">
    <padding>
        <Insets top="15" right="12" bottom="15" left="12"/>
    </padding>
    
    <!-- Mode Selection -->
    <VBox spacing="8" styleClass="mode-selection">
        <Label text="MODES" styleClass="sidebar-section-title"/>
        
        <!-- Horizontal layout: icon beside text -->
        <Button fx:id="encoderModeButton" onAction="#handleEncoderMode" 
                styleClass="mode-button, selected" maxWidth="Infinity">
            <graphic>
                <HBox alignment="CENTER_LEFT" spacing="8">
                    <Label styleClass="mode-icon-inline">
                        <!-- Icon set via Java with FontIcon -->
                    </Label>
                    <Label text="Encoder" styleClass="mode-label-inline"/>
                </HBox>
            </graphic>
        </Button>
        
        <!-- Similar for other mode buttons -->
    </VBox>
</VBox>
```

### 5.4 Sidebar CSS

```css
.sidebar {
    -fx-background-color: linear-gradient(to bottom, #1c1c1e 0%, #141416 100%);
    -fx-border-color: transparent rgba(58, 58, 60, 0.5) transparent transparent;
    -fx-border-width: 0 1 0 0;
    -fx-effect: dropshadow(gaussian, rgba(0, 0, 0, 0.4), 12, 0, 4, 0);
    -fx-min-width: 140px;
    -fx-pref-width: 155px;
    -fx-max-width: 180px;
}

.mode-button {
    -fx-background-color: rgba(44, 44, 46, 0.4);
    -fx-border-color: rgba(58, 58, 60, 0.5);
    -fx-border-width: 1;
    -fx-border-radius: 6;
    -fx-background-radius: 6;
    -fx-padding: 10 12;
    -fx-cursor: hand;
    -fx-min-height: 40px;
    -fx-pref-height: 40px;
    -fx-alignment: center-left;
}

.mode-icon-inline {
    -fx-font-size: 14px;
    -fx-text-fill: #ffffff;
    -fx-min-width: 14px;
    -fx-pref-width: 14px;
}

.mode-label-inline {
    -fx-font-size: 13px;
    -fx-font-weight: 500;
    -fx-text-fill: #ffffff;
}

.mode-button.selected {
    -fx-background-color: rgba(10, 132, 255, 0.25);
    -fx-border-color: #0a84ff;
    -fx-border-width: 1.5;
}

.mode-button.selected .mode-icon-inline,
.mode-button.selected .mode-label-inline {
    -fx-text-fill: #0a84ff;
}
```

### 5.5 Java Changes for Icons

```java
private void initializeToolbarIcons() {
    // Update mode buttons with inline icons
    setupModeButton(encoderModeButton, FontAwesomeSolid.VIDEO, "Encoder");
    setupModeButton(subtitleModeButton, FontAwesomeSolid.CLOSED_CAPTIONING, "Subtitles");
    setupModeButton(renamerModeButton, FontAwesomeSolid.FOLDER, "Metadata");
    setupModeButton(settingsButton, FontAwesomeSolid.COG, "Settings");
}

private void setupModeButton(Button button, FontAwesomeSolid icon, String text) {
    HBox container = new HBox(8);
    container.setAlignment(Pos.CENTER_LEFT);
    
    FontIcon fontIcon = new FontIcon(icon);
    fontIcon.setIconSize(14);
    Label iconLabel = new Label();
    iconLabel.setGraphic(fontIcon);
    iconLabel.getStyleClass().add("mode-icon-inline");
    
    Label textLabel = new Label(text);
    textLabel.getStyleClass().add("mode-label-inline");
    
    container.getChildren().addAll(iconLabel, textLabel);
    button.setGraphic(container);
    button.setText(null); // Remove text, use graphic only
}
```

---

## 6. Settings Integration

### 6.1 Convert Dialog to Mode View

**Current**: SettingsDialog opens as modal dialog
**New**: Settings as 4th mode in main view

### 6.2 Settings Mode Layout

```xml
<!-- Settings Mode Layout (in MainView.fxml) -->
<BorderPane fx:id="settingsModeLayout" managed="false" visible="false" styleClass="main-split-pane">
    
    <!-- Left: Category Navigation -->
    <left>
        <VBox styleClass="settings-nav" prefWidth="200">
            <ListView fx:id="settingsCategoryList" styleClass="category-list">
                <items>
                    <FXCollections fx:factory="observableArrayList">
                        <String fx:value="General"/>
                        <String fx:value="Encoding"/>
                        <String fx:value="Subtitles"/>
                        <String fx:value="Metadata"/>
                        <String fx:value="FFmpeg"/>
                        <String fx:value="Advanced"/>
                        <String fx:value="About"/>
                    </FXCollections>
                </items>
            </ListView>
        </VBox>
    </left>
    
    <!-- Center: Settings Content -->
    <center>
        <ScrollPane fitToWidth="true" styleClass="settings-scroll">
            <VBox fx:id="settingsContent" spacing="24" styleClass="settings-content">
                <padding>
                    <Insets top="24" right="32" bottom="24" left="32"/>
                </padding>
                
                <!-- Settings panels loaded dynamically -->
            </VBox>
        </ScrollPane>
    </center>
    
</BorderPane>
```

### 6.3 Settings Navigation

```java
private void handleSettingsMode() {
    currentMode = "settings";
    showModeLayout(settingsModeLayout);
    updateModeButtonSelection(settingsButton);
    loadSettingsCategory("General");
}

private void loadSettingsCategory(String category) {
    settingsContent.getChildren().clear();
    
    switch (category) {
        case "General":
            settingsContent.getChildren().add(createGeneralSettings());
            break;
        case "Encoding":
            settingsContent.getChildren().add(createEncodingSettings());
            break;
        case "About":
            settingsContent.getChildren().add(createAboutPanel());
            break;
        // etc.
    }
}

private VBox createAboutPanel() {
    VBox about = new VBox(16);
    about.getStyleClass().add("settings-panel");
    
    Label title = new Label("About EncodeForge");
    title.getStyleClass().add("settings-category-title");
    
    Label version = new Label("Version 0.4.0");
    version.getStyleClass().add("settings-version");
    
    // Add update check button
    Button checkUpdates = new Button("Check for Updates");
    checkUpdates.setOnAction(e -> handleCheckForUpdates());
    
    // Add view logs button
    Button viewLogs = new Button("View Logs Folder");
    viewLogs.setOnAction(e -> handleOpenLogsFolder());
    
    about.getChildren().addAll(title, version, checkUpdates, viewLogs);
    return about;
}
```

---

## 7. Table Improvements

### 7.1 Add Order/Index Column

```java
private void setupQueuedTable() {
    // Add index column
    TableColumn<ConversionJob, Integer> indexColumn = new TableColumn<>("#");
    indexColumn.setCellValueFactory(cd -> 
        new SimpleIntegerProperty(queuedTable.getItems().indexOf(cd.getValue()) + 1).asObject());
    indexColumn.setPrefWidth(40);
    indexColumn.setMaxWidth(50);
    indexColumn.setMinWidth(35);
    indexColumn.setResizable(false);
    indexColumn.setSortable(false);
    indexColumn.getStyleClass().add("index-column");
    
    queuedTable.getColumns().add(0, indexColumn);
    
    // ... rest of setup
}
```

### 7.2 Auto-Resize Columns

```java
private void setupTableAutoResize() {
    // Set column resize policy
    queuedTable.setColumnResizePolicy(TableView.CONSTRAINED_RESIZE_POLICY);
    
    // Or manual distribution
    queuedTable.widthProperty().addListener((obs, oldWidth, newWidth) -> {
        double tableWidth = newWidth.doubleValue();
        
        // Fixed width columns
        double fixedWidth = 40 + 35 + 70 + 80; // #, status, output, size
        
        // Remaining width for filename
        double remainingWidth = tableWidth - fixedWidth;
        queuedFileColumn.setPrefWidth(remainingWidth);
    });
}
```

### 7.3 Improved Table Styling

```css
/* Index column */
.index-column {
    -fx-alignment: center;
    -fx-text-fill: #a0a0a0;
    -fx-font-size: 11px;
    -fx-font-weight: 600;
}

/* Table column resizing */
.queue-table .column-header {
    -fx-padding: 8 12;
}

.queue-table .table-column {
    -fx-alignment: center-left;
}

.queue-table .table-cell {
    -fx-padding: 6 12;
}

/* Better borders */
.queue-table {
    -fx-border-color: rgba(58, 58, 60, 0.6);
    -fx-border-width: 1;
    -fx-border-radius: 4;
}
```

---

## 8. Depth & Animation

### 8.1 Shadow System

```css
:root {
    /* Elevation shadows */
    --elevation-0: none;
    --elevation-1: 0 1px 3px rgba(0, 0, 0, 0.12), 
                   0 1px 2px rgba(0, 0, 0, 0.24);
    --elevation-2: 0 3px 6px rgba(0, 0, 0, 0.16), 
                   0 3px 6px rgba(0, 0, 0, 0.23);
    --elevation-3: 0 10px 20px rgba(0, 0, 0, 0.19), 
                   0 6px 6px rgba(0, 0, 0, 0.23);
    --elevation-4: 0 14px 28px rgba(0, 0, 0, 0.25), 
                   0 10px 10px rgba(0, 0, 0, 0.22);
    --elevation-5: 0 19px 38px rgba(0, 0, 0, 0.30), 
                   0 15px 12px rgba(0, 0, 0, 0.22);
}

/* Apply to components */
.mode-panel {
    -fx-effect: var(--elevation-2);
}

.button:hover {
    -fx-effect: var(--elevation-3);
}

.dialog-pane {
    -fx-effect: var(--elevation-5);
}
```

### 8.2 Transition Animations

```css
/* Smooth transitions */
.button {
    -fx-transition: all 0.15s ease-out;
}

.button:hover {
    -fx-scale-x: 1.02;
    -fx-scale-y: 1.02;
    -fx-transition: all 0.15s ease-out;
}

.mode-button {
    -fx-transition: background-color 0.2s ease, 
                    border-color 0.2s ease,
                    transform 0.15s ease;
}

.table-row-cell:hover {
    -fx-background-color: rgba(0, 120, 212, 0.15);
    -fx-transition: background-color 0.1s ease;
}
```

### 8.3 Gradient Depth

```css
/* Subtle gradients for depth */
.custom-title-bar {
    -fx-background-color: linear-gradient(to bottom, 
        rgba(28, 28, 30, 0.98) 0%, 
        rgba(24, 24, 26, 0.98) 100%);
}

.sidebar {
    -fx-background-color: linear-gradient(to bottom, 
        #1c1c1e 0%, 
        #141416 100%);
}

.mode-panel {
    -fx-background-color: linear-gradient(to bottom, 
        rgba(28, 28, 30, 0.95) 0%, 
        rgba(28, 28, 30, 0.98) 100%);
}

.button {
    -fx-background-color: linear-gradient(to bottom, 
        #3a3a3c 0%, 
        #2c2c2e 100%);
}

.primary-button {
    -fx-background-color: linear-gradient(to bottom, 
        #0a84ff 0%, 
        #0066cc 100%);
}
```

### 8.4 Hover Effects

```css
/* Interactive feedback */
.button:hover {
    -fx-background-color: linear-gradient(to bottom, 
        #48484a 0%, 
        #3a3a3c 100%);
    -fx-border-color: rgba(10, 132, 255, 0.5);
    -fx-cursor: hand;
}

.mode-button:hover {
    -fx-background-color: rgba(10, 132, 255, 0.15);
    -fx-border-color: rgba(10, 132, 255, 0.4);
}

.table-row-cell:hover {
    -fx-background-color: rgba(0, 120, 212, 0.15);
}

/* Pressed states */
.button:pressed {
    -fx-scale-x: 0.98;
    -fx-scale-y: 0.98;
    -fx-effect: innershadow(gaussian, rgba(0, 0, 0, 0.4), 4, 0, 0, 1);
}
```

---

## 9. Component Fixes

### 9.1 Spinner Text Cutoff Fix

```css
.spinner {
    -fx-background-color: #252525;
    -fx-border-color: #3a3a3a;
    -fx-border-width: 1;
    -fx-border-radius: 4;
    -fx-background-radius: 4;
    -fx-min-height: 32px;
    -fx-pref-height: 32px;
}

.spinner .text-field {
    -fx-background-color: transparent;
    -fx-border-width: 0;
    -fx-text-fill: #ffffff;
    -fx-font-size: 12px;
    -fx-padding: 2 8; /* Reduced internal padding */
    -fx-min-width: 70px; /* Ensure enough space */
    -fx-alignment: center-right; /* Align numbers right */
    -fx-text-alignment: right;
}

/* Arrow buttons */
.spinner .increment-arrow-button,
.spinner .decrement-arrow-button {
    -fx-background-color: #2d2d2d;
    -fx-border-color: #3a3a3a;
    -fx-pref-width: 18px;
    -fx-padding: 0;
}

.spinner .increment-arrow,
.spinner .decrement-arrow {
    -fx-background-color: #a0a0a0;
    -fx-padding: 2;
}
```

### 9.2 ComboBox Improvements

```css
.combo-box {
    -fx-background-color: #252525;
    -fx-border-color: #3a3a3a;
    -fx-border-width: 1;
    -fx-border-radius: 4;
    -fx-background-radius: 4;
    -fx-min-height: 32px;
    -fx-pref-height: 32px;
    -fx-font-size: 12px;
}

.combo-box .list-cell {
    -fx-background-color: transparent;
    -fx-text-fill: #ffffff;
    -fx-padding: 4 10;
    -fx-font-size: 12px;
}

.combo-box .arrow-button {
    -fx-background-color: transparent;
    -fx-padding: 0 8;
}

.combo-box .arrow {
    -fx-background-color: #a0a0a0;
    -fx-shape: "M 0 0 L 4 4 L 8 0 Z";
    -fx-scale-shape: true;
    -fx-padding: 4;
}
```

### 9.3 TextField Improvements

```css
.text-field {
    -fx-background-color: rgba(28, 28, 30, 0.8);
    -fx-text-fill: #ffffff;
    -fx-border-color: rgba(72, 72, 74, 0.4);
    -fx-border-width: 1;
    -fx-border-radius: 4;
    -fx-background-radius: 4;
    -fx-padding: 8 12;
    -fx-font-size: 13px;
    -fx-min-height: 36px;
    -fx-pref-height: 36px;
}

.text-field:focused {
    -fx-background-color: rgba(28, 28, 30, 1.0);
    -fx-border-color: #0a84ff;
    -fx-border-width: 2;
}

/* Prompt text */
.text-field:empty {
    -fx-prompt-text-fill: rgba(160, 160, 160, 0.7);
}
```

---

## 10. FXML Modifications

### 10.1 Remove Unnecessary Menu Bar

**Option 1**: Remove completely and move functions to Settings

```xml
<!-- Remove this entire MenuBar section -->
<MenuBar styleClass="main-menu-bar" HBox.hgrow="ALWAYS">
    <!-- ... -->
</MenuBar>
```

**Option 2**: Replace with minimal 3-dot menu

```xml
<Region HBox.hgrow="ALWAYS" onMousePressed="#handleTitleBarPressed" 
        onMouseDragged="#handleTitleBarDragged" styleClass="draggable-spacer"/>

<!-- 3-dot menu button -->
<Button fx:id="menuButton" styleClass="menu-button" onAction="#handleMenu">
    <graphic>
        <Label text="⋮" styleClass="menu-icon"/>
    </graphic>
</Button>
```

### 10.2 Update Mode Layouts

Add Settings mode layout:

```xml
<StackPane fx:id="mainContentStack">
    <!-- Existing encoder/subtitle/renamer layouts -->
    
    <!-- Settings Mode Layout -->
    <BorderPane fx:id="settingsModeLayout" managed="false" visible="false" 
                styleClass="main-split-pane">
        <!-- Settings content as described in section 6.2 -->
    </BorderPane>
</StackPane>
```

### 10.3 Update Sidebar Structure

```xml
<VBox fx:id="sidebar" styleClass="sidebar" minWidth="140" prefWidth="155" maxWidth="180">
    <padding>
        <Insets top="15" right="12" bottom="15" left="12"/>
    </padding>
    
    <!-- App Header -->
    <VBox spacing="4" styleClass="sidebar-header">
        <Label fx:id="appIconLabel" styleClass="app-icon-sidebar"/>
        <Label text="EncodeForge" styleClass="app-title-sidebar"/>
    </VBox>
    
    <!-- Mode Selection (includes Settings now) -->
    <VBox spacing="8" styleClass="mode-selection">
        <Label text="MODES" styleClass="sidebar-section-title"/>
        
        <Button fx:id="encoderModeButton" onAction="#handleEncoderMode" 
                styleClass="mode-button, selected" maxWidth="Infinity">
            <!-- Updated structure with horizontal layout -->
        </Button>
        
        <Button fx:id="subtitleModeButton" onAction="#handleSubtitleMode" 
                styleClass="mode-button" maxWidth="Infinity"/>
        
        <Button fx:id="renamerModeButton" onAction="#handleRenamerMode" 
                styleClass="mode-button" maxWidth="Infinity"/>
        
        <Button fx:id="settingsButton" onAction="#handleSettingsMode" 
                styleClass="mode-button" maxWidth="Infinity"/>
    </VBox>
    
    <Separator styleClass="sidebar-separator"/>
    
    <!-- File Operations -->
    <VBox spacing="8" styleClass="file-operations">
        <Label text="FILES" styleClass="sidebar-section-title"/>
        <Button fx:id="addFilesButton" onAction="#handleAddFiles" 
                styleClass="mode-button" maxWidth="Infinity"/>
        <Button fx:id="addFolderButton" onAction="#handleAddFolder" 
                styleClass="mode-button" maxWidth="Infinity"/>
    </VBox>
    
    <Region VBox.vgrow="ALWAYS"/>
    
    <Separator styleClass="sidebar-separator"/>
    
    <!-- FFmpeg Status Card -->
    <VBox spacing="8" styleClass="ffmpeg-status-section">
        <Label text="STATUS" styleClass="sidebar-section-title"/>
        <Button fx:id="ffmpegStatusButton" onAction="#handleFFmpegStatus" 
                styleClass="ffmpeg-status-button">
            <!-- Compact status display -->
        </Button>
    </VBox>
</VBox>
```

---

## 11. Java Code Changes

### 11.1 New Constants

```java
public class MainController {
    // Update sizing constants
    private static final double MIN_WIDTH_RATIO = 0.6;
    private static final double MIN_HEIGHT_RATIO = 0.7;
    private static final double ABSOLUTE_MIN_WIDTH = 900;
    private static final double ABSOLUTE_MIN_HEIGHT = 600;
    
    // Icon sizes (now smaller and consistent)
    private static final int WINDOW_CONTROL_ICON_SIZE = 12;
    private static final int TOOLBAR_ICON_SIZE = 14;
    private static final int SIDEBAR_ICON_SIZE = 14;
    private static final int SMALL_ICON_SIZE = 10;
    
    // Add settingsModeLayout
    @FXML private BorderPane settingsModeLayout;
    @FXML private ListView<String> settingsCategoryList;
    @FXML private VBox settingsContent;
}
```

### 11.2 Initialize Method Updates

```java
@FXML
public void initialize() {
    logger.info("Initializing Main Controller");
    
    // Initialize all icons with new sizes
    initializeWindowControlIcons();
    initializeToolbarIcons();
    initializeSidebarIcons(); // New method
    
    setupQueueTable();
    setupQueueDragAndDrop();
    setupQueueSplitPane();
    setupUIBindings();
    setupQuickSettings();
    setupPreviewTabs();
    setupSubtitleFileSelector();
    setupSubtitleProgressBar();
    setupSettingsMode(); // New method
    setupResponsiveResize(); // New method
    
    // Set default mode to encoder
    handleEncoderMode();
    
    // Defer status check
    CompletableFuture.runAsync(() -> {
        try {
            Thread.sleep(500);
            updateAllStatus();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    });
    
    // Check for ongoing conversions
    CompletableFuture.runAsync(this::checkForOngoingConversions);
    
    logger.info("Main Controller initialized");
}
```

### 11.3 New Settings Mode Handler

```java
@FXML
private void handleSettingsMode() {
    currentMode = "settings";
    showModePanel(null); // Hide quick settings panels
    showModeLayout(settingsModeLayout);
    updateModeButtonSelection(settingsButton);
    loadSettingsCategory("General");
    log("Switched to settings mode");
}

private void setupSettingsMode() {
    if (settingsCategoryList != null) {
        settingsCategoryList.getSelectionModel().selectedItemProperty()
            .addListener((obs, oldVal, newVal) -> {
                if (newVal != null) {
                    loadSettingsCategory(newVal);
                }
            });
    }
}

private void loadSettingsCategory(String category) {
    if (settingsContent == null) return;
    
    settingsContent.getChildren().clear();
    
    switch (category) {
        case "General":
            settingsContent.getChildren().add(createGeneralSettings());
            break;
        case "Encoding":
            settingsContent.getChildren().add(createEncodingSettings());
            break;
        case "Subtitles":
            settingsContent.getChildren().add(createSubtitleSettings());
            break;
        case "Metadata":
            settingsContent.getChildren().add(createMetadataSettings());
            break;
        case "FFmpeg":
            settingsContent.getChildren().add(createFFmpegSettings());
            break;
        case "Advanced":
            settingsContent.getChildren().add(createAdvancedSettings());
            break;
        case "About":
            settingsContent.getChildren().add(createAboutPanel());
            break;
    }
}
```

### 11.4 Responsive Window Sizing

```java
private void setupResponsiveResize() {
    if (primaryStage == null) return;
    
    // Get screen dimensions
    Rectangle2D screenBounds = Screen.getPrimary().getVisualBounds();
    
    // Calculate responsive minimum sizes
    double minWidth = Math.max(
        screenBounds.getWidth() * MIN_WIDTH_RATIO, 
        ABSOLUTE_MIN_WIDTH
    );
    double minHeight = Math.max(
        screenBounds.getHeight() * MIN_HEIGHT_RATIO, 
        ABSOLUTE_MIN_HEIGHT
    );
    
    // Apply constraints
    primaryStage.setMinWidth(minWidth);
    primaryStage.setMinHeight(minHeight);
    
    // Set initial size based on screen
    if (primaryStage.getWidth() < minWidth || primaryStage.getHeight() < minHeight) {
        primaryStage.setWidth(Math.min(screenBounds.getWidth() * 0.8, 1400));
        primaryStage.setHeight(Math.min(screenBounds.getHeight() * 0.85, 900));
        primaryStage.centerOnScreen();
    }
}
```

### 11.5 Update showModeLayout

```java
private void showModeLayout(javafx.scene.layout.Region layout) {
    // Hide all layouts
    if (encoderModeLayout != null) {
        encoderModeLayout.setVisible(false);
        encoderModeLayout.setManaged(false);
    }
    if (subtitleModeLayout != null) {
        subtitleModeLayout.setVisible(false);
        subtitleModeLayout.setManaged(false);
    }
    if (renamerModeLayout != null) {
        renamerModeLayout.setVisible(false);
        renamerModeLayout.setManaged(false);
    }
    if (settingsModeLayout != null) {
        settingsModeLayout.setVisible(false);
        settingsModeLayout.setManaged(false);
    }
    
    // Show selected layout
    if (layout != null) {
        layout.setVisible(true);
        layout.setManaged(true);
    }
}
```

---

## 12. Testing Strategy

### 12.1 Screen Resolution Testing

Test on multiple resolutions:
- ✓ 1024x768 (minimum supported)
- ✓ 1280x720 (HD)
- ✓ 1366x768 (common laptop)
- ✓ 1920x1080 (Full HD)
- ✓ 2560x1440 (2K)
- ✓ 3840x2160 (4K)

### 12.2 Component Testing Checklist

- [ ] All buttons have proper hover/press states
- [ ] All text is readable at all sizes
- [ ] No text cutoff in any components
- [ ] Tables auto-resize properly
- [ ] Spinners display numbers fully
- [ ] ComboBoxes open correctly
- [ ] Sidebar icons align with text
- [ ] Mode switching works smoothly
- [ ] Settings mode displays correctly
- [ ] Splash screen animates properly

### 12.3 Cross-Platform Testing

- [ ] Windows 10/11
- [ ] Ubuntu 20.04/22.04
- [ ] macOS (if possible)

### 12.4 Performance Testing

- [ ] UI loads in < 2 seconds
- [ ] Mode switching is instant
- [ ] No lag during animations
- [ ] Memory usage acceptable
- [ ] Theme switching responsive

---

## Implementation Order

### Phase 1: Foundation (Days 1-2)
1. Create new responsive CSS with variables
2. Implement media queries
3. Update typography system
4. Fix component sizing issues

### Phase 2: Visual Improvements (Days 3-4)
5. Add depth with shadows/gradients
6. Implement hover animations
7. Update color system
8. Enhance splash screen

### Phase 3: Layout Redesign (Days 5-6)
9. Redesign sidebar (horizontal layout)
10. Update FXML structure
11. Add settings mode layout
12. Fix table columns

### Phase 4: Integration (Days 7-8)
13. Update Java code for new layouts
14. Implement theme system foundation
15. Test on multiple resolutions
16. Fix bugs and polish

### Phase 5: Final Polish (Days 9-10)
17. Final visual refinements
18. Performance optimization
19. Documentation
20. Release preparation

---

## Files to Modify

### CSS Files
- `application.css` - Complete rewrite with responsive design

### FXML Files
- `MainView.fxml` - Update sidebar, add settings mode, remove menu bar
- `InitializationDialog.fxml` - Enhanced splash screen

### Java Files
- `MainController.java` - New handlers, responsive sizing, settings mode
- `MainApp.java` - Theme system integration
- New: `ThemeManager.java` - Theme loading/validation
- New: `SettingsViewController.java` - Settings mode controller

### New Files
- `themes/default-dark/theme.json`
- `themes/default-dark/colors.css`
- `themes/default-dark/typography.css`
- `themes/default-dark/components.css`

---

## Success Criteria

1. ✅ Application scales properly on screens from 1024x768 to 4K
2. ✅ All text remains readable without truncation
3. ✅ UI has Apple/macOS-level polish with proper depth
4. ✅ Sidebar uses horizontal icon+text layout
5. ✅ Settings integrated as mode view, not dialog
6. ✅ Tables auto-resize columns to fill space
7. ✅ Spinner/increment fields display numbers fully
8. ✅ Theme system foundation ready for expansion
9. ✅ Smooth animations and transitions throughout
10. ✅ Enhanced splash screen with branding

---

## Notes

- Prioritize backward compatibility
- Keep existing functionality intact
- Document all major changes
- Maintain performance
- Test thoroughly before release

---

**Document Version**: 1.0  
**Created**: 2025-01-24  
**Last Updated**: 2025-01-24  
**Author**: EncodeForge Development Team
