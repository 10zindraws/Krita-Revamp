/*
 *  SPDX-FileCopyrightText: 2002 Patrick Julien <freak@codepimps.org>
 *  SPDX-FileCopyrightText: 2009 Sven Langkamp <sven.langkamp@gmail.com>
 *  SPDX-FileCopyrightText: 2011 Silvio Heinrich <plassy@web.de>
 *  SPDX-FileCopyrightText: 2011 Srikanth Tiyyagura <srikanth.tulasiram@gmail.com>
 *  SPDX-FileCopyrightText: 2011 José Luis Vergara <pentalis@gmail.com>
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 */

#include "kis_preset_chooser.h"

#include <QVBoxLayout>
#include <QPainter>
#include <QAbstractItemDelegate>
#include <QStyleOptionViewItem>
#include <QSortFilterProxyModel>
#include <KisResourceModel.h>
#include <QApplication>

#include <kis_config.h>
#include <klocalizedstring.h>
#include <KisKineticScroller.h>

#include <KoIcon.h>
#include <KisResourceItemChooser.h>
#include <KisResourceItemChooserSync.h>
#include <KisResourceItemListView.h>
#include <KisResourceLocator.h>
#include <KisResourceTypes.h>

#include <brushengine/kis_paintop_settings.h>
#include <brushengine/kis_paintop_preset.h>
#include "kis_config_notifier.h"
#include <kis_icon.h>
#include <KisResourceModelProvider.h>
#include <KisTagFilterResourceProxyModel.h>
#include <KisResourceThumbnailCache.h>
#include "KisBrushStrokePreviewCache.h"
#include "KisBrushStrokePreviewGenerator.h"


/// The resource item delegate for rendering the resource preview
class KisPresetDelegate : public QAbstractItemDelegate
{
public:
    KisPresetDelegate(QObject * parent = 0)
        : QAbstractItemDelegate(parent)
        , m_showText(false)
        , m_viewMode(KisPresetChooser::THUMBNAIL) {}

    ~KisPresetDelegate() override {}

    /// reimplemented
    void paint(QPainter *, const QStyleOptionViewItem &, const QModelIndex &) const override;

    /// reimplemented
    QSize sizeHint(const QStyleOptionViewItem & option, const QModelIndex &) const override {
        return option.decorationSize;
    }

    void setShowText(bool showText) {
        m_showText = showText;
    }

    void setViewMode(KisPresetChooser::ViewMode mode) {
        m_viewMode = mode;
    }

    KisPresetChooser::ViewMode viewMode() const {
        return m_viewMode;
    }

private:
    void paintThumbnail(QPainter *painter, const QStyleOptionViewItem &option, const QModelIndex &index) const;
    void paintStrokePreview(QPainter *painter, const QStyleOptionViewItem &option, const QModelIndex &index) const;

    bool m_showText;
    KisPresetChooser::ViewMode m_viewMode;
};

void KisPresetDelegate::paint(QPainter * painter, const QStyleOptionViewItem & option, const QModelIndex & index) const
{
    painter->save();
    painter->setRenderHint(QPainter::SmoothPixmapTransform, true);
    if (!(option.state & QStyle::State_Enabled)) {
        painter->setOpacity(0.2);
    }

    if (!index.isValid()) {
        painter->restore();
        return;
    }

    // Dispatch to appropriate paint method based on view mode
    if (m_viewMode == KisPresetChooser::STROKE) {
        paintStrokePreview(painter, option, index);
    } else {
        paintThumbnail(painter, option, index);
    }

    painter->restore();
}

void KisPresetDelegate::paintThumbnail(QPainter *painter, const QStyleOptionViewItem &option, const QModelIndex &index) const
{
    bool dirty = index.data(Qt::UserRole + KisAbstractResourceModel::Dirty).toBool();

    QImage preview = KisResourceThumbnailCache::instance()->getImage(index);

    if (preview.isNull()) {
        preview = QImage(512, 512, QImage::Format_RGB32);
        preview.fill(Qt::red);
    }

    qreal devicePixelRatioF = painter->device()->devicePixelRatioF();

    QRect paintRect = option.rect.adjusted(1, 1, -1, -1);
    if (!m_showText) {
        QImage previewHighDpi =
            KisResourceThumbnailCache::instance()->getImage(index,
                                                             paintRect.size() * devicePixelRatioF,
                                                             Qt::IgnoreAspectRatio,
                                                             Qt::SmoothTransformation);
        previewHighDpi.setDevicePixelRatio(devicePixelRatioF);
        painter->drawImage(paintRect.x(), paintRect.y(), previewHighDpi);
    }
    else {
        QSize pixSize(paintRect.height(), paintRect.height());
        QImage previewHighDpi = KisResourceThumbnailCache::instance()->getImage(index,
                                                                                 pixSize * devicePixelRatioF,
                                                                                 Qt::KeepAspectRatio,
                                                                                 Qt::SmoothTransformation);
        previewHighDpi.setDevicePixelRatio(devicePixelRatioF);
        painter->drawImage(paintRect.x(), paintRect.y(), previewHighDpi);

        // Put an asterisk after the preset if it is dirty. This will help in case the pixmap icon is too small

        QString dirtyPresetIndicator = QString("");
        if (dirty) {
            dirtyPresetIndicator = QString("*");
        }

        QString presetDisplayName = index.data(Qt::UserRole + KisAbstractResourceModel::Name).toString().replace("_", " ");
        painter->drawText(pixSize.width() + 10, option.rect.y() + option.rect.height() - 10, presetDisplayName.append(dirtyPresetIndicator));

    }

    if (dirty) {
        const QIcon icon = KisIconUtils::loadIcon("dirty-preset");
        QPixmap pixmap = icon.pixmap(QSize(16,16));
        painter->drawPixmap(paintRect.x() + 3, paintRect.y() + 3, pixmap);
    }

    bool broken = false;
    QMap<QString, QVariant> metaData = index.data(Qt::UserRole + KisAbstractResourceModel::MetaData).value<QMap<QString, QVariant>>();
    QStringList requiredBrushes = metaData["dependent_resources_filenames"].toStringList();
    if (!requiredBrushes.isEmpty()) {
        KisAllResourcesModel *model = KisResourceModelProvider::resourceModel(ResourceType::Brushes);
        Q_FOREACH(const QString brushFile, requiredBrushes) {
            if (!model->resourceExists("", brushFile, "")) {
                qWarning() << "dependent resource" << brushFile << "misses.";
                broken = true;
            }
        }
    }

    if (broken) {
        const QIcon icon = KisIconUtils::loadIcon("broken-preset");
        icon.paint(painter, QRect(paintRect.x() + paintRect.height() - 25, paintRect.y() + paintRect.height() - 25, 25, 25));
    }

    if (option.state & QStyle::State_Selected) {
        painter->setCompositionMode(QPainter::CompositionMode_HardLight);
        painter->setOpacity(1.0);
        painter->fillRect(option.rect, option.palette.highlight());

        // highlight is not strong enough to pick out preset. draw border around it.
        painter->setCompositionMode(QPainter::CompositionMode_SourceOver);
        painter->setPen(QPen(option.palette.highlight(), 4, Qt::SolidLine, Qt::FlatCap, Qt::MiterJoin));
        QRect selectedBorder = option.rect.adjusted(2 , 2, -2, -2);
        painter->drawRect(selectedBorder);
    }
}

void KisPresetDelegate::paintStrokePreview(QPainter *painter, const QStyleOptionViewItem &option, const QModelIndex &index) const
{
    bool dirty = index.data(Qt::UserRole + KisAbstractResourceModel::Dirty).toBool();

    // Get the brush preset from the model
    KoResourceSP resource;
    const KisAbstractResourceModel *resourceModel = dynamic_cast<const KisAbstractResourceModel*>(index.model());
    if (resourceModel) {
        resource = resourceModel->resourceForIndex(index);
    }
    KisPaintOpPresetSP preset = resource.dynamicCast<KisPaintOpPreset>();

    qreal devicePixelRatioF = painter->device()->devicePixelRatioF();

    // Colors for stroke preview mode
    const QColor backgroundColor(0x53, 0x53, 0x53);  // #535353
    const QColor borderColor(0x45, 0x45, 0x45);      // #454545
    const QColor textColor(0xCC, 0xCC, 0xCC);        // Light gray text

    // Draw border around the entire cell
    painter->fillRect(option.rect, borderColor);

    // Inner rect after 2px border
    QRect innerRect = option.rect.adjusted(2, 2, -2, -2);

    // Fill with background color
    painter->fillRect(innerRect, backgroundColor);

    // Calculate stroke preview area (leave space for text at bottom)
    const int textHeight = 18;  // Height reserved for brush name
    QRect strokeRect = innerRect;
    strokeRect.setHeight(innerRect.height() - textHeight);

    QSize previewSize = strokeRect.size() * devicePixelRatioF;

    QImage strokePreview;
    if (preset) {
        // Get cached stroke preview or generate new one
        strokePreview = KisBrushStrokePreviewCache::instance()->getPreview(preset, previewSize);
    }

    if (strokePreview.isNull()) {
        // Fallback: draw a placeholder
        strokePreview = QImage(previewSize, QImage::Format_ARGB32_Premultiplied);
        strokePreview.fill(backgroundColor);
    }

    strokePreview.setDevicePixelRatio(devicePixelRatioF);

    // Draw the stroke preview
    painter->drawImage(strokeRect.topLeft(), strokePreview);

    // Draw the preset name below the stroke
    QString presetDisplayName = index.data(Qt::UserRole + KisAbstractResourceModel::Name).toString().replace("_", " ");
    if (dirty) {
        presetDisplayName.append("*");
    }

    // Elide text if too long
    QFontMetrics fm(painter->font());
    QString elidedName = fm.elidedText(presetDisplayName, Qt::ElideRight, innerRect.width() - 4);

    QRect textRect = innerRect;
    textRect.setTop(strokeRect.bottom());
    painter->setPen(textColor);
    painter->drawText(textRect, Qt::AlignCenter, elidedName);

    // Draw dirty indicator
    if (dirty) {
        const QIcon icon = KisIconUtils::loadIcon("dirty-preset");
        QPixmap pixmap = icon.pixmap(QSize(16, 16));
        painter->drawPixmap(innerRect.x() + 3, innerRect.y() + 3, pixmap);
    }

    // Check for broken preset
    bool broken = false;
    QMap<QString, QVariant> metaData = index.data(Qt::UserRole + KisAbstractResourceModel::MetaData).value<QMap<QString, QVariant>>();
    QStringList requiredBrushes = metaData["dependent_resources_filenames"].toStringList();
    if (!requiredBrushes.isEmpty()) {
        KisAllResourcesModel *model = KisResourceModelProvider::resourceModel(ResourceType::Brushes);
        Q_FOREACH(const QString brushFile, requiredBrushes) {
            if (!model->resourceExists("", brushFile, "")) {
                broken = true;
                break;
            }
        }
    }

    if (broken) {
        const QIcon icon = KisIconUtils::loadIcon("broken-preset");
        icon.paint(painter, QRect(innerRect.right() - 25, innerRect.y() + 3, 22, 22));
    }

    // Draw selection highlight
    if (option.state & QStyle::State_Selected) {
        painter->setCompositionMode(QPainter::CompositionMode_HardLight);
        painter->setOpacity(1.0);
        painter->fillRect(option.rect, option.palette.highlight());

        // Draw border
        painter->setCompositionMode(QPainter::CompositionMode_SourceOver);
        painter->setPen(QPen(option.palette.highlight(), 4, Qt::SolidLine, Qt::FlatCap, Qt::MiterJoin));
        QRect selectedBorder = option.rect.adjusted(2, 2, -2, -2);
        painter->drawRect(selectedBorder);
    }
}

KisPresetChooser::KisPresetChooser(QWidget *parent)
    : QWidget(parent)
{
    setObjectName("KisPresetChooser");

    QVBoxLayout * layout = new QVBoxLayout(this);
    layout->setMargin(0);

    m_chooser = new KisResourceItemChooser(ResourceType::PaintOpPresets, false, this);
    m_chooser->setRowHeight(50);
    m_delegate = new KisPresetDelegate(this);
    m_chooser->setItemDelegate(m_delegate);
    m_chooser->setSynced(true);
    m_chooser->showImportExportBtns(false);
    layout->addWidget(m_chooser);

    connect(m_chooser, SIGNAL(resourceSelected(KoResourceSP )),
            this, SLOT(slotResourceWasSelected(KoResourceSP )));

    connect(m_chooser, SIGNAL(resourceSelected(KoResourceSP )),
            this, SIGNAL(resourceSelected(KoResourceSP )));
    connect(m_chooser, SIGNAL(resourceClicked(KoResourceSP )),
            this, SIGNAL(resourceClicked(KoResourceSP )));

    connect(m_chooser, &KisResourceItemChooser::listViewModeChanged, this, &KisPresetChooser::showHideBrushNames);

    // Connect to stroke preview cache to update view when previews are ready
    connect(KisBrushStrokePreviewCache::instance(), &KisBrushStrokePreviewCache::previewReady,
            this, &KisPresetChooser::slotStrokePreviewReady);

    m_mode = ViewMode::THUMBNAIL;

    connect(KisConfigNotifier::instance(), SIGNAL(configChanged()),
            SLOT(notifyConfigChanged()));


    notifyConfigChanged();
}

KisPresetChooser::~KisPresetChooser()
{
}

void KisPresetChooser::setViewMode(KisPresetChooser::ViewMode mode)
{
    m_mode = mode;
    updateViewSettings();
}

void KisPresetChooser::setViewModeToThumbnail()
{
    setViewMode(KisPresetChooser::ViewMode::THUMBNAIL);
}

void KisPresetChooser::setViewModeToDetail()
{
    setViewMode(KisPresetChooser::ViewMode::DETAIL);
}

void KisPresetChooser::setViewModeToStroke()
{
    setViewMode(KisPresetChooser::ViewMode::STROKE);
}

void KisPresetChooser::notifyConfigChanged()
{
    KisConfig cfg(true);
    setIconSize(cfg.presetIconSize());
}

void KisPresetChooser::slotResourceWasSelected(KoResourceSP resource)
{
    m_currentPresetConnections.clear();
    if (!resource) return;

    KisPaintOpPresetSP preset = resource.dynamicCast<KisPaintOpPreset>();
    KIS_SAFE_ASSERT_RECOVER_RETURN(preset);

    m_currentPresetConnections.addUniqueConnection(
        preset->updateProxy(), SIGNAL(sigSettingsChanged()),
        this, SLOT(slotCurrentPresetChanged()));
}

void KisPresetChooser::slotCurrentPresetChanged()
{
    KoResourceSP currentResource = m_chooser->currentResource();
    if (!currentResource) return;

    // Invalidate stroke preview cache for this preset
    KisBrushStrokePreviewCache::instance()->invalidatePreset(currentResource->name());

    QModelIndex index = m_chooser->tagFilterModel()->indexForResource(currentResource);
    Q_EMIT m_chooser->tagFilterModel()->dataChanged(index,
                                               index,
                                               {Qt::UserRole + KisAbstractResourceModel::Thumbnail});
}

void KisPresetChooser::updateViewSettings()
{
    switch (m_mode) {
    case ViewMode::THUMBNAIL: {
        m_chooser->setListViewMode(ListViewMode::IconGrid);
        m_delegate->setShowText(false);
        m_delegate->setViewMode(ViewMode::THUMBNAIL);
        break;
    }
    case ViewMode::DETAIL: {
        m_chooser->setListViewMode(ListViewMode::Detail);
        m_delegate->setShowText(true);
        m_delegate->setViewMode(ViewMode::DETAIL);
        break;
    }
    case ViewMode::STROKE: {
        // Use Detail list view mode for horizontal rectangles with name
        m_chooser->setListViewMode(ListViewMode::Detail);
        m_delegate->setShowText(false);  // We draw text ourselves in stroke mode
        m_delegate->setViewMode(ViewMode::STROKE);

        // Pre-generate all stroke previews in the background
        // Use a reasonable default size for the preview
        QSize previewSize = m_chooser->itemView()->iconSize();
        if (!previewSize.isEmpty()) {
            qreal devicePixelRatio = m_chooser->itemView()->devicePixelRatioF();
            previewSize *= devicePixelRatio;
            KisBrushStrokePreviewCache::instance()->preGenerateAllPreviews(previewSize);
        }
        break;
    }
    }
}

void KisPresetChooser::setCurrentResource(KoResourceSP resource)
{
    m_chooser->setCurrentResource(resource);
}

KoResourceSP KisPresetChooser::currentResource() const
{
    return m_chooser->currentResource();
}

void KisPresetChooser::showTaggingBar(bool show)
{
    m_chooser->showTaggingBar(show);
}

KisResourceItemChooser *KisPresetChooser::itemChooser()
{
    return m_chooser;
}

void KisPresetChooser::setPresetFilter(const QString& paintOpId)
{
    QMap<QString, QVariant> metaDataFilter;
    if (!paintOpId.isEmpty()) { // empty means "all"
        metaDataFilter["paintopid"] = paintOpId;
    }
    m_chooser->tagFilterModel()->setMetaDataFilter(metaDataFilter);
    updateViewSettings();
}

void KisPresetChooser::setIconSize(int newSize)
{
    KisResourceItemChooserSync* chooserSync = KisResourceItemChooserSync::instance();
    chooserSync->setBaseLength(newSize);
}

int KisPresetChooser::iconSize()
{
    KisResourceItemChooserSync* chooserSync = KisResourceItemChooserSync::instance();
    return chooserSync->baseLength();
}

void KisPresetChooser::saveIconSize()
{
    // save icon size
    if (KisConfig(true).presetIconSize() != iconSize()) {
        KisConfig(false).setPresetIconSize(iconSize());
    }
}

void KisPresetChooser::showHideBrushNames(ListViewMode newViewMode)
{
    // In STROKE mode, we always draw text ourselves (ignore view mode changes)
    if (m_mode == ViewMode::STROKE) {
        m_delegate->setShowText(false);
        return;
    }

    switch (newViewMode) {
    case ListViewMode::Detail: {
        m_delegate->setShowText(true);
        break;
    }
    default: {
        m_delegate->setShowText(false);
    }
    }
}

void KisPresetChooser::slotStrokePreviewReady(const QString &presetName)
{
    Q_UNUSED(presetName);

    // Only update if we're in stroke mode
    if (m_mode == ViewMode::STROKE) {
        // Trigger a repaint of the view
        m_chooser->itemView()->viewport()->update();
    }
}
