/*
 *  SPDX-FileCopyrightText: 2026 Tenzin Rangdol <tenzindraws@gmail.com>
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 */

#ifndef KIS_BRUSH_TAG_SELECTOR_WIDGET_H
#define KIS_BRUSH_TAG_SELECTOR_WIDGET_H

#include <QWidget>
#include <QList>
#include <QPushButton>
#include <QButtonGroup>

#include <KisTag.h>
#include <kritaui_export.h>

class KisTagModel;
class KisFlowLayout;
class KisTagChooserWidget;

/**
 * @brief Widget that displays brush preset tags as clickable buttons in a flow layout.
 *
 * This widget provides a compact way to switch between brush preset tags.
 * Tags are displayed as checkable buttons that wrap to new rows as needed.
 * Right-clicking a tag button opens the tag management context menu.
 */
class KRITAUI_EXPORT KisBrushTagSelectorWidget : public QWidget
{
    Q_OBJECT

public:
    explicit KisBrushTagSelectorWidget(QWidget *parent = nullptr);
    ~KisBrushTagSelectorWidget() override;

    /**
     * @brief Set the tag model to use for displaying tags.
     * @param model The KisTagModel for brush presets.
     */
    void setTagModel(KisTagModel *model);

    /**
     * @brief Set the tag chooser widget to sync with.
     * @param tagChooser The KisTagChooserWidget that manages tag selection.
     */
    void setTagChooserWidget(KisTagChooserWidget *tagChooser);

    /**
     * @brief Get the currently selected tag.
     * @return The selected tag, or nullptr if no tag is selected.
     */
    KisTagSP currentTag() const;

public Q_SLOTS:
    /**
     * @brief Set the current tag by updating the button selection.
     * @param tag The tag to select.
     */
    void setCurrentTag(KisTagSP tag);

Q_SIGNALS:
    /**
     * @brief Emitted when a tag is selected by clicking a button.
     * @param tag The selected tag.
     */
    void tagSelected(KisTagSP tag);

    /**
     * @brief Emitted when the widget's size hint changes (e.g., when rows are added/removed).
     */
    void sizeHintChanged();

protected:
    void contextMenuEvent(QContextMenuEvent *event) override;
    bool event(QEvent *event) override;

private Q_SLOTS:
    void onButtonClicked(QAbstractButton *button);
    void rebuildButtons();
    void onModelRowsInserted(const QModelIndex &parent, int first, int last);
    void onModelRowsRemoved(const QModelIndex &parent, int first, int last);
    void onModelReset();

private:
    void clearButtons();
    void createButton(KisTagSP tag);
    void syncButtonSelection();
    QSize previousSizeHint() const;
    void checkSizeHintChanged();

    KisFlowLayout *m_flowLayout;
    QButtonGroup *m_buttonGroup;
    QList<QPushButton *> m_buttons;
    KisTagModel *m_tagModel;
    KisTagChooserWidget *m_tagChooser;
    KisTagSP m_currentTag;
    bool m_isUpdating;
    QSize m_previousSizeHint;
};

#endif // KIS_BRUSH_TAG_SELECTOR_WIDGET_H
