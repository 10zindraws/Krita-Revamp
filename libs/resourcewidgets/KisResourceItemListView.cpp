/* This file is part of the KDE project
 * SPDX-FileCopyrightText: 2019 Wolthera van Hövell tot Westerflier <griffinvalley@gmail.com>
 * SPDX-FileCopyrightText: 2026 Tenzin Rangdol tenzindraws@gmail.com
 *
 * SPDX-License-Identifier: LGPL-2.0-or-later
 */

#include "KisResourceItemListView.h"

#include <QEvent>
#include <QScroller>
#include <QScrollBar>
#include <QHelpEvent>
#include <QMouseEvent>
#include <QDrag>
#include <QMimeData>
#include <QPainter>
#include <QApplication>
#include <QDebug>

#include <KisResourceModel.h>

#include "KisIconToolTip.h"

// Visual constants for drag highlighting (matching preset_groups style)
static const QColor HIGHLIGHT_COLOR(70, 170, 255, 255);
static const int LEFT_EDGE_WIDTH = 6;
static const int RIGHT_EDGE_WIDTH = 6;

struct Q_DECL_HIDDEN KisResourceItemListView::Private
{
    ListViewMode viewMode = ListViewMode::IconGrid;
    bool strictSelectionMode {false};
    KisIconToolTip tip;

    QScroller* scroller {0};
    QString prev_scrollbar_style;

    QSize requestedItemSize = QSize(64, 64);

    // Drag-drop state
    bool dragReorderEnabled {false};
    bool isDragging {false};
    bool potentialDrag {false};          // True when we might start a drag
    bool clickedOnSelected {false};      // True if clicked item was already selected
    QPoint dragStartPosition;
    QModelIndex dragStartIndex;
    int dragStartResourceId {-1};        // Stable ID captured at mouse press (survives model updates)
    QModelIndex dropTargetIndex;
    KisResourceItemListView::DropZone dropZone {KisResourceItemListView::DropNone};
    QList<int> draggedResourceIds;       // Track IDs of items being dragged
    QTimer *dragHighlightTimer {nullptr};
};

KisResourceItemListView::KisResourceItemListView(QWidget *parent)
    : QListView(parent)
    , m_d(new Private)
{
    setSelectionMode(QAbstractItemView::ExtendedSelection);
    setContextMenuPolicy(Qt::DefaultContextMenu);
    setResizeMode(QListView::Adjust);
    setUniformItemSizes(true);

    // Default configuration
    setViewMode(QListView::IconMode);
    setGridSize(QSize(64, 64));
    setIconSize(QSize(64, 64));

    // Enable drag-drop
    setDragEnabled(false); // We handle drag manually
    setAcceptDrops(true);
    setDropIndicatorShown(false); // We draw our own indicator

    m_d->scroller = KisKineticScroller::createPreconfiguredScroller(this);
    if (m_d->scroller) {
        connect(m_d->scroller, SIGNAL(stateChanged(QScroller::State)), this, SLOT(slotScrollerStateChange(QScroller::State)));
    }

    connect(this, SIGNAL(clicked(QModelIndex)), SIGNAL(currentResourceClicked(const QModelIndex &)));

    m_d->prev_scrollbar_style = horizontalScrollBar()->styleSheet();

    // Timer for smooth drag highlight updates
    m_d->dragHighlightTimer = new QTimer(this);
    m_d->dragHighlightTimer->setInterval(16); // ~60fps
    connect(m_d->dragHighlightTimer, &QTimer::timeout, this, &KisResourceItemListView::updateDragHighlight);
}

KisResourceItemListView::~KisResourceItemListView()
{
}

void KisResourceItemListView::setListViewMode(ListViewMode viewMode)
{
    m_d->viewMode = viewMode;

    auto restoreScrollbar = [&, this] () {
        horizontalScrollBar()->setStyleSheet(m_d->prev_scrollbar_style);
        setVerticalScrollBarPolicy(Qt::ScrollBarPolicy::ScrollBarAsNeeded);
    };

    switch (viewMode) {
    case ListViewMode::IconGrid: {
        setViewMode(ViewMode::IconMode);
        setFlow(Flow::LeftToRight);
        setWrapping(true);
        restoreScrollbar();

        setItemSize(m_d->requestedItemSize);
        break;
    }
    case ListViewMode::IconStripHorizontal: {
        setViewMode(ViewMode::IconMode);
        setFlow(Flow::LeftToRight);
        setWrapping(false);

        // this is the only way to hide it and not have it ocupy space
        horizontalScrollBar()->setStyleSheet("QScrollBar::horizontal {height: 0px;}");
        setVerticalScrollBarPolicy(Qt::ScrollBarPolicy::ScrollBarAlwaysOff);

        setItemSize(m_d->requestedItemSize);
        break;
    }
    case ListViewMode::Detail: {
        setViewMode(ViewMode::ListMode);
        setFlow(Flow::TopToBottom);
        setWrapping(false);
        restoreScrollbar();

        setItemSize(m_d->requestedItemSize);
        break;
    }
    }
}

void KisResourceItemListView::setItemSize(QSize size)
{
    m_d->requestedItemSize = size;

    switch (m_d->viewMode) {
    case ListViewMode::IconGrid: {
        setGridSize(size);
        setIconSize(size);
        break;
    }
    case ListViewMode::IconStripHorizontal: {
        // you can not set the item size in strip mode
        // it is configured automatically based on size
        break;
    }
    case ListViewMode::Detail: {
        const int w = width() - horizontalScrollBar()->width();
        setGridSize(QSize(w, size.height()));
        setIconSize(QSize(size));
        break;
    }
    }
}

void KisResourceItemListView::setStrictSelectionMode(bool enable)
{
    m_d->strictSelectionMode = enable;
    if (enable) {
        setSelectionMode(QAbstractItemView::SingleSelection);
    } else {
        setSelectionMode(QAbstractItemView::ExtendedSelection);
    }
}

void KisResourceItemListView::setDragReorderEnabled(bool enable)
{
    m_d->dragReorderEnabled = enable;
}

bool KisResourceItemListView::isDragReorderEnabled() const
{
    return m_d->dragReorderEnabled;
}

void KisResourceItemListView::setFixedToolTipThumbnailSize(const QSize &size)
{
    m_d->tip.setFixedToolTipThumbnailSize(size);
}

void KisResourceItemListView::setToolTipShouldRenderCheckers(bool value)
{
    m_d->tip.setToolTipShouldRenderCheckers(value);
}

QList<int> KisResourceItemListView::getSelectedResourceIds() const
{
    QList<int> ids;
    QModelIndexList selected = selectionModel()->selectedIndexes();
    for (const QModelIndex &idx : selected) {
        int id = idx.data(Qt::UserRole + KisAbstractResourceModel::Id).toInt();
        if (id > 0) {
            ids.append(id);
        }
    }
    return ids;
}

void KisResourceItemListView::rowsAboutToBeRemoved(const QModelIndex &parent, int start, int end)
{
    // QAbstractItemView moves the current index if the row it points to is removed,
    // which we don't want for strict selections
    QModelIndex current = currentIndex();
    if (selectionMode() == SingleSelection
            && m_d->strictSelectionMode
            && current.isValid()
            && current.row() >= start
            && current.row() <= end) {

        selectionModel()->clear();
    }
    QListView::rowsAboutToBeRemoved(parent, start, end);
}

void KisResourceItemListView::selectionChanged(const QItemSelection &selected, const QItemSelection &deselected)
{
    // base class takes care of viewport updates
    QListView::selectionChanged(selected, deselected);

    if (selected.isEmpty()) {
        Q_EMIT currentResourceChanged(QModelIndex());
    }
    else {
        Q_EMIT currentResourceChanged(selected.indexes().first());
    }
}

QItemSelectionModel::SelectionFlags KisResourceItemListView::selectionCommand(const QModelIndex &index, const QEvent *event) const
{
    QItemSelectionModel::SelectionFlags cmd = QListView::selectionCommand(index, event);

    // avoid deselecting the current item by Ctrl-clicking in single selection mode
    if (selectionMode() == SingleSelection
            && m_d->strictSelectionMode
            && cmd.testFlag(QItemSelectionModel::Deselect)) {

        cmd = QItemSelectionModel::NoUpdate;
    }
    return cmd;
}

void KisResourceItemListView::contextMenuEvent(QContextMenuEvent *event)
{
    QListView::contextMenuEvent(event);
    Q_EMIT contextMenuRequested(event->globalPos());
}

bool KisResourceItemListView::viewportEvent(QEvent *event)
{
    if (!model()) return true;

    if (event->type() == QEvent::ToolTip) {
        QHelpEvent *he = static_cast<QHelpEvent *>(event);
        QStyleOptionViewItem option = viewOptions();
        QModelIndex index = model()->buddy(indexAt(he->pos()));
        if (index.isValid()) {
            option.rect = visualRect(index);
            m_d->tip.showTip(this, he->pos(), option, index);
            return true;
        }
        m_d->tip.hide();
    }

    return QListView::viewportEvent(event);
}

void KisResourceItemListView::mousePressEvent(QMouseEvent *event)
{
    if (event->button() == Qt::LeftButton && m_d->dragReorderEnabled) {
        m_d->dragStartPosition = event->pos();
        m_d->dragStartIndex = indexAt(event->pos());
        m_d->potentialDrag = false;
        m_d->clickedOnSelected = false;
        m_d->dragStartResourceId = -1;

        if (m_d->dragStartIndex.isValid()) {
            // Capture resource ID BEFORE any selection changes
            // (selection changes can trigger model updates that invalidate the index)
            m_d->dragStartResourceId = m_d->dragStartIndex.data(Qt::UserRole + KisAbstractResourceModel::Id).toInt();

            // Check if clicked item is already selected
            m_d->clickedOnSelected = selectionModel()->isSelected(m_d->dragStartIndex);

            // If no modifier keys, we might be starting a drag
            // Handle selection ourselves to prevent rubber band from appearing
            if (!(event->modifiers() & (Qt::ControlModifier | Qt::ShiftModifier))) {
                m_d->potentialDrag = true;

                if (m_d->clickedOnSelected) {
                    // Item already selected - don't change selection yet
                    // Use NoUpdate flag to set current index WITHOUT changing selection
                    selectionModel()->setCurrentIndex(m_d->dragStartIndex, QItemSelectionModel::NoUpdate);
                } else {
                    // Item not selected - select it immediately (this becomes the drag item)
                    // This also prevents rubber band since we handle selection ourselves
                    selectionModel()->select(m_d->dragStartIndex,
                        QItemSelectionModel::ClearAndSelect | QItemSelectionModel::Current);
                }
                // Don't call parent - this prevents rubber band initialization
                return;
            }
        }
    }
    QListView::mousePressEvent(event);
}

void KisResourceItemListView::mouseMoveEvent(QMouseEvent *event)
{
    if (!m_d->dragReorderEnabled) {
        QListView::mouseMoveEvent(event);
        return;
    }

    if (!(event->buttons() & Qt::LeftButton)) {
        QListView::mouseMoveEvent(event);
        return;
    }

    if (!m_d->dragStartIndex.isValid()) {
        QListView::mouseMoveEvent(event);
        return;
    }

    // Check if we've moved far enough to start a drag
    int distance = (event->pos() - m_d->dragStartPosition).manhattanLength();
    if (distance < QApplication::startDragDistance()) {
        // Don't call parent if we're in potential drag mode
        // This prevents rubber band selection from starting
        if (!m_d->potentialDrag) {
            QListView::mouseMoveEvent(event);
        }
        return;
    }

    // Start drag - don't call parent's mouseMoveEvent to prevent rubber band
    if (!m_d->isDragging) {
        startDrag();
    }
    // Note: We explicitly don't call QListView::mouseMoveEvent here
    // to prevent rubber band selection interference
}

void KisResourceItemListView::mouseReleaseEvent(QMouseEvent *event)
{
    bool wasDragging = m_d->isDragging;
    bool wasPotentialDrag = m_d->potentialDrag;
    QModelIndex clickedIndex = m_d->dragStartIndex;

    if (m_d->isDragging) {
        stopDrag();
    }

    // Reset drag state
    m_d->dragStartIndex = QModelIndex();
    m_d->potentialDrag = false;

    // If we were in potential drag mode but didn't actually drag,
    // finalize the selection (ensures only this item is selected, clearing any multi-selection)
    if (wasPotentialDrag && !wasDragging && clickedIndex.isValid()) {
        if (event->button() == Qt::LeftButton &&
            !(event->modifiers() & (Qt::ControlModifier | Qt::ShiftModifier))) {
            // Single click without drag = ensure only this item is selected
            // This clears multi-selection if clicking on one of multiple selected items
            selectionModel()->select(clickedIndex,
                QItemSelectionModel::ClearAndSelect | QItemSelectionModel::Current);
        }
        // Don't call parent - we've handled the release ourselves
        return;
    }

    QListView::mouseReleaseEvent(event);
}

void KisResourceItemListView::startDrag()
{
    m_d->isDragging = true;
    m_d->potentialDrag = false;  // We're now actually dragging
    m_d->dragHighlightTimer->start();

    // Get selected items for drag
    QList<int> resourceIds = getSelectedResourceIds();

    // Ensure the drag start item is included (use stored ID since index may be stale)
    if (m_d->dragStartResourceId > 0 && !resourceIds.contains(m_d->dragStartResourceId)) {
        // Item under cursor wasn't in selection - use only it
        resourceIds.clear();
        resourceIds.append(m_d->dragStartResourceId);
    }

    if (resourceIds.isEmpty()) {
        stopDrag();
        return;
    }

    // Store dragged resource IDs for no-op detection
    m_d->draggedResourceIds = resourceIds;

    // Create mime data
    QMimeData *mimeData = new QMimeData();
    QStringList idStrings;
    for (int id : resourceIds) {
        idStrings.append(QString::number(id));
    }
    mimeData->setData("application/x-krita-resourceids", idStrings.join(",").toUtf8());

    // Create drag object
    QDrag *drag = new QDrag(this);
    drag->setMimeData(mimeData);

    // Set drag pixmap - find current index for the resource ID
    if (model()) {
        for (int row = 0; row < model()->rowCount(); ++row) {
            QModelIndex idx = model()->index(row, 0);
            if (idx.data(Qt::UserRole + KisAbstractResourceModel::Id).toInt() == m_d->dragStartResourceId) {
                QPixmap pixmap = idx.data(Qt::DecorationRole).value<QIcon>().pixmap(32, 32);
                if (!pixmap.isNull()) {
                    drag->setPixmap(pixmap);
                    drag->setHotSpot(QPoint(16, 16));
                }
                break;
            }
        }
    }

    // Execute drag - this blocks until drop or cancel
    drag->exec(Qt::MoveAction);

    stopDrag();
}

void KisResourceItemListView::stopDrag()
{
    m_d->isDragging = false;
    m_d->potentialDrag = false;
    m_d->clickedOnSelected = false;
    m_d->dragStartResourceId = -1;
    m_d->dragHighlightTimer->stop();
    m_d->dropTargetIndex = QModelIndex();
    m_d->dropZone = DropNone;
    m_d->draggedResourceIds.clear();
    viewport()->update();
}

void KisResourceItemListView::dragEnterEvent(QDragEnterEvent *event)
{
    if (!m_d->dragReorderEnabled) {
        event->ignore();
        return;
    }

    if (event->mimeData()->hasFormat("application/x-krita-resourceids")) {
        event->acceptProposedAction();
    } else {
        event->ignore();
    }
}

void KisResourceItemListView::dragMoveEvent(QDragMoveEvent *event)
{
    if (!m_d->dragReorderEnabled) {
        event->ignore();
        return;
    }

    if (!event->mimeData()->hasFormat("application/x-krita-resourceids")) {
        event->ignore();
        return;
    }

    event->acceptProposedAction();

    // Update drop target for visual feedback
    QModelIndex idx = indexAt(event->pos());
    if (idx.isValid()) {
        DropZone zone = getDropZone(event->pos(), idx);

        // Only update drop target if we're in an active zone (not no-op)
        if (zone != DropNone) {
            m_d->dropTargetIndex = idx;
            m_d->dropZone = zone;
        } else {
            // In no-op zone - clear drop target (no visual feedback)
            m_d->dropTargetIndex = QModelIndex();
            m_d->dropZone = DropNone;
        }
    } else {
        // Dropped on empty area - append to end
        m_d->dropTargetIndex = QModelIndex();
        m_d->dropZone = DropNone;
    }

    viewport()->update();
}

void KisResourceItemListView::dragLeaveEvent(QDragLeaveEvent *event)
{
    Q_UNUSED(event);
    m_d->dropTargetIndex = QModelIndex();
    viewport()->update();
}

void KisResourceItemListView::dropEvent(QDropEvent *event)
{
    if (!m_d->dragReorderEnabled) {
        event->ignore();
        return;
    }

    if (!event->mimeData()->hasFormat("application/x-krita-resourceids")) {
        event->ignore();
        return;
    }

    event->acceptProposedAction();

    // Parse resource IDs from mime data
    QByteArray data = event->mimeData()->data("application/x-krita-resourceids");
    QStringList idStrings = QString::fromUtf8(data).split(",");
    QList<int> resourceIds;
    for (const QString &str : idStrings) {
        bool ok;
        int id = str.toInt(&ok);
        if (ok && id > 0) {
            resourceIds.append(id);
        }
    }

    if (resourceIds.isEmpty()) {
        m_d->dropTargetIndex = QModelIndex();
        viewport()->update();
        return;
    }

    // Get the target item and drop zone
    QModelIndex targetIdx = indexAt(event->pos());
    DropZone zone = targetIdx.isValid() ? getDropZone(event->pos(), targetIdx) : DropNone;

    // If in no-op zone, do nothing
    if (zone == DropNone && targetIdx.isValid()) {
        m_d->dropTargetIndex = QModelIndex();
        m_d->dropZone = DropNone;
        viewport()->update();
        return;
    }

    // Get the target item's resource ID
    int targetItemId = -1;
    bool insertAfter = false;

    if (targetIdx.isValid()) {
        targetItemId = targetIdx.data(Qt::UserRole + KisAbstractResourceModel::Id).toInt();
        insertAfter = (zone == DropAfter);
    }
    // If targetIdx is invalid (dropped on empty area), targetItemId = -1 means append to end

    // Emit signal with target item ID and insert position
    Q_EMIT resourcesReordered(resourceIds, targetItemId, insertAfter);

    // Clear drop target
    m_d->dropTargetIndex = QModelIndex();
    m_d->dropZone = DropNone;
    viewport()->update();
}

int KisResourceItemListView::calculateDropPosition(const QPoint &pos) const
{
    QModelIndex idx = indexAt(pos);
    if (!idx.isValid()) {
        // Dropped on empty area - append to end
        return model() ? model()->rowCount() : 0;
    }

    DropZone zone = getDropZone(pos, idx);

    // No-op zone - return -1 to signal no action
    if (zone == DropNone) {
        return -1;
    }

    int row = idx.row();
    if (zone == DropAfter) {
        // Drop on right/bottom edge means insert after this item
        row++;
    }
    // zone == DropBefore means insert at current row (before this item)

    return row;
}

bool KisResourceItemListView::isSingleColumnLayout() const
{
    if (!model() || model()->rowCount() == 0) {
        return false;
    }

    // Detail mode is always single column
    if (m_d->viewMode == ListViewMode::Detail) {
        return true;
    }

    // For IconGrid/Strip modes, check if items are arranged in a single column
    // by comparing X coordinates of first few visible items
    QModelIndex firstIdx = indexAt(viewport()->rect().topLeft());
    if (!firstIdx.isValid()) {
        firstIdx = model()->index(0, 0);
    }

    if (!firstIdx.isValid()) {
        return false;
    }

    QRect firstRect = visualRect(firstIdx);
    int referenceX = firstRect.left();
    int tolerance = firstRect.width() / 4; // 25% tolerance for alignment

    // Check next few items to see if they're in the same column
    int itemsToCheck = qMin(5, model()->rowCount());
    int matchingColumn = 0;

    for (int i = 0; i < itemsToCheck; i++) {
        QModelIndex idx = model()->index(firstIdx.row() + i, 0);
        if (!idx.isValid()) break;

        QRect rect = visualRect(idx);
        if (qAbs(rect.left() - referenceX) <= tolerance) {
            matchingColumn++;
        }
    }

    // If most items share the same X coordinate, it's a single column
    return matchingColumn >= itemsToCheck - 1;
}

KisResourceItemListView::DropZone KisResourceItemListView::getDropZone(const QPoint &pos, const QModelIndex &index) const
{
    QRect rect = visualRect(index);
    if (!rect.isValid()) return DropNone;

    // Edge zone threshold: 30% from each edge
    const double edgeThreshold = 0.30;

    // Determine if we should use vertical (top/bottom) or horizontal (left/right) logic
    bool useSingleColumnLogic = isSingleColumnLayout();

    if (useSingleColumnLogic) {
        // Single column: use top/bottom edges
        int height = rect.height();
        int topEdgeEnd = rect.top() + static_cast<int>(height * edgeThreshold);
        int bottomEdgeStart = rect.bottom() - static_cast<int>(height * edgeThreshold);

        if (pos.y() <= topEdgeEnd) {
            return DropBefore; // Top edge
        } else if (pos.y() >= bottomEdgeStart) {
            return DropAfter; // Bottom edge
        } else {
            return DropNone; // Middle no-op zone
        }
    } else {
        // Multi-column: use left/right edges
        int width = rect.width();
        int leftEdgeEnd = rect.left() + static_cast<int>(width * edgeThreshold);
        int rightEdgeStart = rect.right() - static_cast<int>(width * edgeThreshold);

        if (pos.x() <= leftEdgeEnd) {
            return DropBefore; // Left edge
        } else if (pos.x() >= rightEdgeStart) {
            return DropAfter; // Right edge
        } else {
            return DropNone; // Middle no-op zone
        }
    }
}

void KisResourceItemListView::paintEvent(QPaintEvent *event)
{
    QListView::paintEvent(event);

    // Draw drop indicator if we have a valid drop target and not in no-op zone
    if (m_d->dropTargetIndex.isValid() && m_d->isDragging && m_d->dropZone != DropNone) {
        QPainter painter(viewport());
        drawDropIndicator(&painter, m_d->dropTargetIndex, m_d->dropZone);
    }
}

void KisResourceItemListView::drawDropIndicator(QPainter *painter, const QModelIndex &index, DropZone zone)
{
    if (zone == DropNone) return; // Don't draw indicator for no-op zone

    QRect rect = visualRect(index);
    if (!rect.isValid()) return;

    painter->save();
    painter->setRenderHint(QPainter::Antialiasing, true);

    QPen pen(HIGHLIGHT_COLOR);
    pen.setWidth(zone == DropBefore ? LEFT_EDGE_WIDTH : RIGHT_EDGE_WIDTH);
    painter->setPen(pen);
    painter->setBrush(Qt::NoBrush);

    // Determine if we should draw horizontal (top/bottom) or vertical (left/right) lines
    bool useSingleColumnLogic = isSingleColumnLayout();

    if (useSingleColumnLogic) {
        // Single column: draw horizontal lines (top/bottom)
        int y = (zone == DropBefore) ? rect.top() + LEFT_EDGE_WIDTH / 2 : rect.bottom() - RIGHT_EDGE_WIDTH / 2;
        painter->drawLine(rect.left(), y, rect.right(), y);
    } else {
        // Multi-column: draw vertical lines (left/right)
        int x = (zone == DropBefore) ? rect.left() + LEFT_EDGE_WIDTH / 2 : rect.right() - RIGHT_EDGE_WIDTH / 2;
        painter->drawLine(x, rect.top(), x, rect.bottom());
    }

    painter->restore();
}

void KisResourceItemListView::updateDragHighlight()
{
    // This is called during drag to update the visual highlight
    // The actual update is done in dragMoveEvent, this just ensures smooth updates
    if (m_d->isDragging) {
        viewport()->update();
    }
}

void KisResourceItemListView::resizeEvent(QResizeEvent *event)
{
    QListView::resizeEvent(event);

    switch (m_d->viewMode) {
    case ListViewMode::IconStripHorizontal: {
        const int height = event->size().height();
        setGridSize(QSize(height, height));
        setIconSize(QSize(height, height));
        break;
    }
    case ListViewMode::Detail: {
        setItemSize(m_d->requestedItemSize);
    }
    }
    scrollTo(currentIndex(), QAbstractItemView::PositionAtCenter);
}
