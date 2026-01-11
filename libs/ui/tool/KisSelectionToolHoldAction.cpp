/*
 *  SPDX-FileCopyrightText: 2026 Krita Developers
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 */

#include "KisSelectionToolHoldAction.h"

#include <QApplication>
#include <QAction>
#include <QKeyEvent>
#include <QLineEdit>
#include <QTextEdit>
#include <QPlainTextEdit>
#include <QSpinBox>
#include <QDoubleSpinBox>
#include <QComboBox>

#include <KoToolManager.h>
#include <kis_debug.h>

KisSelectionToolHoldManager *KisSelectionToolHoldManager::s_instance = nullptr;

KisSelectionToolHoldManager::KisSelectionToolHoldManager()
    : QObject()
    , m_trackedKey(0)
    , m_trackedModifiers(Qt::NoModifier)
    , m_installed(false)
{
}

KisSelectionToolHoldManager::~KisSelectionToolHoldManager()
{
}

KisSelectionToolHoldManager* KisSelectionToolHoldManager::instance()
{
    if (!s_instance) {
        s_instance = new KisSelectionToolHoldManager();
    }
    return s_instance;
}

void KisSelectionToolHoldManager::install()
{
    if (!m_installed) {
        qApp->installEventFilter(this);
        m_installed = true;
    }
}

void KisSelectionToolHoldManager::registerToolAction(const QString &toolId, QAction *action)
{
    if (action) {
        m_toolActions.insert(toolId, action);
        dbgUI << "KisSelectionToolHoldManager: Registered tool" << toolId 
              << "with shortcut" << action->shortcut().toString();
    }
}

bool KisSelectionToolHoldManager::matchesShortcut(QKeyEvent *keyEvent, const QKeySequence &shortcut) const
{
    if (shortcut.isEmpty()) {
        return false;
    }
    
    // Build key combination from event
    int key = keyEvent->key();
    Qt::KeyboardModifiers mods = keyEvent->modifiers();
    
    // Ignore modifier-only keys
    if (key == Qt::Key_Shift || key == Qt::Key_Control || 
        key == Qt::Key_Alt || key == Qt::Key_Meta) {
        return false;
    }
    
    // Build the key combination the same way Qt stores it in QKeySequence
    int keyCombination = key;
    if (mods & Qt::ShiftModifier) keyCombination |= Qt::ShiftModifier;
    if (mods & Qt::ControlModifier) keyCombination |= Qt::ControlModifier;
    if (mods & Qt::AltModifier) keyCombination |= Qt::AltModifier;
    if (mods & Qt::MetaModifier) keyCombination |= Qt::MetaModifier;
    
    // Compare with the first key in the shortcut sequence
    // In Qt5, QKeySequence::operator[] returns int with key + modifiers
    int shortcutKey = shortcut[0];
    
    return keyCombination == shortcutKey;
}

void KisSelectionToolHoldManager::switchToTool(const QString &toolId)
{
    KoToolManager::instance()->switchToolRequested(toolId);
}

void KisSelectionToolHoldManager::switchToMoveTool()
{
    dbgUI << "KisSelectionToolHoldManager: Switching to Move Tool";
    KoToolManager::instance()->switchToolRequested("KritaTransform/KisToolMove");
}

bool KisSelectionToolHoldManager::isTextInputWidget(QWidget *widget) const
{
    if (!widget) {
        return false;
    }
    
    // Check if focus is on any text input widget where typing should work normally
    if (qobject_cast<QLineEdit*>(widget) ||
        qobject_cast<QTextEdit*>(widget) ||
        qobject_cast<QPlainTextEdit*>(widget) ||
        qobject_cast<QSpinBox*>(widget) ||
        qobject_cast<QDoubleSpinBox*>(widget)) {
        return true;
    }
    
    // QComboBox with editable mode
    QComboBox *comboBox = qobject_cast<QComboBox*>(widget);
    if (comboBox && comboBox->isEditable()) {
        return true;
    }
    
    // Also check if parent is a spin box (the internal line edit)
    QWidget *parent = widget->parentWidget();
    if (parent) {
        if (qobject_cast<QSpinBox*>(parent) ||
            qobject_cast<QDoubleSpinBox*>(parent) ||
            qobject_cast<QComboBox*>(parent)) {
            return true;
        }
    }
    
    // Check for shortcut configuration widgets by class name
    // (to avoid circular header dependencies)
    const char *className = widget->metaObject()->className();
    if (qstrcmp(className, "KisKKeySequenceWidget") == 0 ||
        qstrcmp(className, "KisInputButton") == 0 ||
        qstrcmp(className, "ShortcutEditWidget") == 0) {
        return true;
    }
    
    // Also check parent widgets for shortcut dialogs
    QWidget *ancestor = widget;
    while (ancestor) {
        const char *ancestorClassName = ancestor->metaObject()->className();
        if (qstrcmp(ancestorClassName, "KisKKeySequenceWidget") == 0 ||
            qstrcmp(ancestorClassName, "KisInputButton") == 0 ||
            qstrcmp(ancestorClassName, "KisShortcutsDialog") == 0 ||
            qstrcmp(ancestorClassName, "ShortcutEditWidget") == 0) {
            return true;
        }
        ancestor = ancestor->parentWidget();
    }
    
    return false;
}

bool KisSelectionToolHoldManager::eventFilter(QObject *watched, QEvent *event)
{
    Q_UNUSED(watched);
    
    // Don't intercept events when focus is on a text input widget
    QWidget *focusWidget = QApplication::focusWidget();
    if (isTextInputWidget(focusWidget)) {
        return QObject::eventFilter(watched, event);
    }
    
    // Handle ShortcutOverride first - this is sent before Qt processes shortcuts
    // If we accept it, Qt won't fire the shortcut and will deliver KeyPress instead
    if (event->type() == QEvent::ShortcutOverride) {
        QKeyEvent *keyEvent = static_cast<QKeyEvent*>(event);
        
        // Check if this key matches any of our registered tool shortcuts
        for (auto it = m_toolActions.constBegin(); it != m_toolActions.constEnd(); ++it) {
            QAction *action = it.value();
            if (action && action->isEnabled() && matchesShortcut(keyEvent, action->shortcut())) {
                dbgUI << "KisSelectionToolHoldManager: ShortcutOverride matched for" << it.key();
                // Accept the event to prevent Qt's shortcut system from handling it
                event->accept();
                return true;
            }
        }
    }
    else if (event->type() == QEvent::KeyPress) {
        QKeyEvent *keyEvent = static_cast<QKeyEvent*>(event);
        
        // Ignore auto-repeat
        if (keyEvent->isAutoRepeat()) {
            return false;
        }
        
        // Check if this key matches any of our registered tool shortcuts
        for (auto it = m_toolActions.constBegin(); it != m_toolActions.constEnd(); ++it) {
            QAction *action = it.value();
            if (action && action->isEnabled() && matchesShortcut(keyEvent, action->shortcut())) {
                const QString &toolId = it.key();
                
                dbgUI << "KisSelectionToolHoldManager: KeyPress matched for" << toolId;
                
                // Start tracking this key press
                m_currentlyTrackedTool = toolId;
                m_trackedKey = keyEvent->key();
                m_trackedModifiers = keyEvent->modifiers();
                m_holdTimer.start();
                
                // Switch to the selection tool immediately
                switchToTool(toolId);
                
                // Consume the event so the normal action doesn't fire
                return true;
            }
        }
    }
    else if (event->type() == QEvent::KeyRelease) {
        QKeyEvent *keyEvent = static_cast<QKeyEvent*>(event);
        
        // Ignore auto-repeat
        if (keyEvent->isAutoRepeat()) {
            return false;
        }
        
        // Check if this is the release of our tracked key
        if (!m_currentlyTrackedTool.isEmpty() && 
            keyEvent->key() == m_trackedKey) {
            
            const qint64 elapsed = m_holdTimer.elapsed();
            QString trackedTool = m_currentlyTrackedTool;
            
            dbgUI << "KisSelectionToolHoldManager: KeyRelease for" << trackedTool 
                  << "after" << elapsed << "ms";
            
            // Reset tracking
            m_currentlyTrackedTool.clear();
            m_trackedKey = 0;
            m_trackedModifiers = Qt::NoModifier;
            
            // If held for 200ms or more, switch to Move Tool
            if (elapsed >= HOLD_THRESHOLD_MS) {
                dbgUI << "KisSelectionToolHoldManager: Hold threshold reached, switching to Move Tool";
                switchToMoveTool();
            }
            // If less than 200ms, stay on the selection tool (already switched on key press)
            
            // Consume the event
            return true;
        }
    }
    
    return QObject::eventFilter(watched, event);
}
