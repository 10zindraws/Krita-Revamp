/*
 *  SPDX-FileCopyrightText: 2026 Krita Developers
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 */

#ifndef KIS_SELECTION_TOOL_HOLD_ACTION_H
#define KIS_SELECTION_TOOL_HOLD_ACTION_H

#include <QObject>
#include <QElapsedTimer>
#include <QHash>
#include <QKeySequence>
#include "kritaui_export.h"

class QKeyEvent;
class QAction;
class QWidget;

/**
 * @brief Singleton manager for selection tool hold detection
 * 
 * This class provides hold detection for selection tool shortcuts.
 * When a selection tool shortcut (Freehand, Elliptical, Rectangular, Polygonal)
 * is held for 200ms or more, releasing the key will switch to the Move Tool
 * instead of staying on the selection tool.
 * 
 * If the key is pressed for less than 200ms, the normal behavior applies
 * (switch to the selection tool and stay).
 * 
 * This class installs itself as an application-wide event filter to intercept
 * key press/release events before they trigger the normal QAction shortcuts.
 */
class KRITAUI_EXPORT KisSelectionToolHoldManager : public QObject
{
    Q_OBJECT
public:
    static KisSelectionToolHoldManager* instance();
    
    /**
     * Install the event filter on the application
     */
    void install();
    
    /**
     * Register a tool action for hold detection
     * @param toolId The tool ID (e.g., "KisToolSelectOutline")
     * @param action The QAction associated with the tool
     */
    void registerToolAction(const QString &toolId, QAction *action);
    
protected:
    bool eventFilter(QObject *watched, QEvent *event) override;

private:
    KisSelectionToolHoldManager();
    ~KisSelectionToolHoldManager() override;
    
    bool matchesShortcut(QKeyEvent *keyEvent, const QKeySequence &shortcut) const;
    bool isTextInputWidget(QWidget *widget) const;
    void switchToTool(const QString &toolId);
    void switchToMoveTool();
    
    static KisSelectionToolHoldManager *s_instance;
    
    // Map from tool ID to action
    QHash<QString, QAction*> m_toolActions;
    
    // Currently tracked key press
    QString m_currentlyTrackedTool;
    QElapsedTimer m_holdTimer;
    int m_trackedKey;
    Qt::KeyboardModifiers m_trackedModifiers;
    bool m_installed;
    
    static const qint64 HOLD_THRESHOLD_MS = 200;
};

#endif // KIS_SELECTION_TOOL_HOLD_ACTION_H
