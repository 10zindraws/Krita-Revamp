/* This file is part of the KDE project
 * SPDX-FileCopyrightText: 2019 Wolthera van Hövell tot Westerflier <griffinvalley@gmail.com>
 * SPDX-FileCopyrightText: 2026 Tenzin Rangdol tenzindraws@gmail.com
 *
 * SPDX-License-Identifier: LGPL-2.0-or-later
 */

#ifndef KISRESOURCEITEMLISTVIEW_H
#define KISRESOURCEITEMLISTVIEW_H

#include <QListView>
#include <QScopedPointer>
#include <QTimer>

#include <KisKineticScroller.h>

#include "kritaresourcewidgets_export.h"
#include "ResourceListViewModes.h"

class KisTagFilterResourceProxyModel;

class KRITARESOURCEWIDGETS_EXPORT KisResourceItemListView : public QListView
{
    Q_OBJECT

public:
    KisResourceItemListView(QWidget *parent = nullptr);
    ~KisResourceItemListView() override;

    void setListViewMode(ListViewMode layout);

    /**
     * @brief setItemSize
     * convenience function which sets both the icon and the grid size
     * to the same value.
     * @param size - the size you wish either to be.
     */
    void setItemSize(QSize size);

    /**
     * @brief setStrictSelectionMode sets additional restrictions on the selection.
     *
     * When in QAbstractItemView::SingleSelection mode, this ensures that the
     * selection never gets transferred to another item. Instead, the selection
     * is cleared if the current item gets removed (filtered) from the model.
     * Furthermore, it prevents users from deselecting the current item with Ctrl+click.
     * This behavior is important for resource selectors.
     * @param enable Determines if strict mode is enabled.
     */
    void setStrictSelectionMode(bool enable);

    /**
     * @brief setDragReorderEnabled Enable/disable drag-drop reordering of items
     * @param enable Whether reordering is enabled
     */
    void setDragReorderEnabled(bool enable);

    /**
     * @brief isDragReorderEnabled Check if drag reordering is enabled
     * @return true if enabled
     */
    bool isDragReorderEnabled() const;

    void setFixedToolTipThumbnailSize(const QSize &size);
    void setToolTipShouldRenderCheckers(bool value);

    /**
     * @brief getSelectedResourceIds Get IDs of all selected resources
     * @return List of resource IDs
     */
    QList<int> getSelectedResourceIds() const;

public Q_SLOTS:
    void slotScrollerStateChange(QScroller::State state){ KisKineticScroller::updateCursor(this, state); }

Q_SIGNALS:

    void sigSizeChanged();

    void currentResourceChanged(const QModelIndex &);
    void currentResourceClicked(const QModelIndex &);

    void contextMenuRequested(const QPoint &);

    /**
     * @brief resourcesReordered Emitted when resources have been reordered via drag-drop
     * @param resourceIds The resource IDs that were moved
     * @param targetPosition The new position (row index)
     */
    void resourcesReordered(const QList<int> &resourceIds, int targetPosition);

protected Q_SLOTS:
    void rowsAboutToBeRemoved(const QModelIndex &parent, int start, int end) override;
    void selectionChanged(const QItemSelection &selected, const QItemSelection &deselected) override;

protected:
    QItemSelectionModel::SelectionFlags selectionCommand(const QModelIndex &index, const QEvent *event = nullptr) const override;
    void contextMenuEvent(QContextMenuEvent *event) override;

    bool viewportEvent(QEvent *event) override;

    // Drag-drop overrides
    void mousePressEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void mouseReleaseEvent(QMouseEvent *event) override;
    void dragEnterEvent(QDragEnterEvent *event) override;
    void dragMoveEvent(QDragMoveEvent *event) override;
    void dragLeaveEvent(QDragLeaveEvent *event) override;
    void dropEvent(QDropEvent *event) override;

    void paintEvent(QPaintEvent *event) override;

private Q_SLOTS:
    void updateDragHighlight();

private:
    void resizeEvent(QResizeEvent *event) override;

    void startDrag();
    void stopDrag();
    int calculateDropPosition(const QPoint &pos) const;
    bool isLeftHalf(const QPoint &pos, const QModelIndex &index) const;
    void drawDropIndicator(QPainter *painter, const QModelIndex &index, bool leftSide);

private:
    struct Private;
    const QScopedPointer<Private> m_d;
};

#endif // KISRESOURCEITEMLISTVIEW_H
