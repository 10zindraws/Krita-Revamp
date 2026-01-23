/*
 *  SPDX-FileCopyrightText: 2016 Dmitry Kazakov <dimula73@gmail.com>
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 */

#include "kis_brush_hud.h"

#include <QGuiApplication>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QPointer>
#include <QLabel>
#include <QPainter>
#include <QPaintEvent>
#include <QScrollArea>
#include <QEvent>
#include <QToolButton>
#include <QAction>
#include <QCheckBox>

#include "kis_uniform_paintop_property.h"
#include "kis_slider_based_paintop_property.h"
#include "kis_uniform_paintop_property_widget.h"
#include "kis_canvas_resource_provider.h"
#include "kis_paintop_preset.h"
#include "kis_paintop_settings.h"
#include "kis_signal_auto_connection.h"
#include "KisPaintOpPresetUpdateProxy.h"
#include "kis_icon_utils.h"
#include "kis_dlg_brush_hud_config.h"
#include "kis_brush_hud_properties_config.h"
#include "kis_elided_label.h"

#include "kis_canvas2.h"
#include "KisViewManager.h"
#include "kactioncollection.h"
#include "KoToolManager.h"
#include "tool/kis_tool_freehand.h"

#include "kis_debug.h"


struct KisBrushHud::Private
{
    QPointer<KisElidedLabel> lblPresetName;
    QPointer<QLabel> lblPresetIcon;
    QPointer<QWidget> wdgProperties;
    QPointer<QScrollArea> wdgPropertiesArea;
    QPointer<QVBoxLayout> propertiesLayout;
    QPointer<QToolButton> btnReloadPreset;
    QPointer<QToolButton> btnConfigure;

    KisCanvasResourceProvider *provider;

    KisSignalAutoConnectionsStore connections;
    KisSignalAutoConnectionsStore presetConnections;

    KisPaintOpPresetSP currentPreset;

    QPointer<QCheckBox> snapToAssistantsCheckbox;
    bool showSnapToAssistants = true; // Whether to show the checkbox
    QList<QPointer<QWidget>> toolOptionWidgets; // Store the current tool option widgets
};

KisBrushHud::KisBrushHud(KisCanvasResourceProvider *provider, QWidget *parent)
    : QWidget(parent, Qt::FramelessWindowHint),
      m_d(new Private)
{
    m_d->provider = provider;

    QVBoxLayout *layout = new QVBoxLayout(this);

    QHBoxLayout *labelLayout = new QHBoxLayout();
    m_d->lblPresetIcon = new QLabel(this);
    const QSize iconSize = QSize(22,22);
    m_d->lblPresetIcon->setMinimumSize(iconSize);
    m_d->lblPresetIcon->setMaximumSize(iconSize);
    m_d->lblPresetIcon->setScaledContents(true);

    m_d->lblPresetName = new KisElidedLabel("<Preset Name>", Qt::ElideMiddle, this);

    m_d->btnReloadPreset = new QToolButton(this);
    m_d->btnReloadPreset->setAutoRaise(true);
    m_d->btnReloadPreset->setToolTip(i18n("Reload Original Preset"));

    m_d->btnConfigure = new QToolButton(this);
    m_d->btnConfigure->setAutoRaise(true);
    m_d->btnConfigure->setToolTip(i18n("Configure the on-canvas brush editor"));

    connect(m_d->btnReloadPreset, SIGNAL(clicked()), SLOT(slotReloadPreset()));
    connect(m_d->btnConfigure, SIGNAL(clicked()), SLOT(slotConfigBrushHud()));

    labelLayout->addWidget(m_d->lblPresetIcon);
    labelLayout->addWidget(m_d->lblPresetName);
    labelLayout->addWidget(m_d->btnReloadPreset);
    labelLayout->addWidget(m_d->btnConfigure);

    layout->addLayout(labelLayout);

    m_d->wdgPropertiesArea = new QScrollArea(this);
    m_d->wdgPropertiesArea->setAlignment(Qt::AlignLeft | Qt::AlignTop);
    m_d->wdgPropertiesArea->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);

    m_d->wdgPropertiesArea->setWidgetResizable(true);

    m_d->wdgProperties = new QWidget(this);
    m_d->propertiesLayout = new QVBoxLayout(m_d->wdgProperties);
    m_d->propertiesLayout->setSpacing(0);
    m_d->propertiesLayout->setContentsMargins(0, 0, 22, 0);
    m_d->propertiesLayout->setSizeConstraint(QLayout::SetMinimumSize);

    // not adding any widgets until explicitly requested

    m_d->wdgPropertiesArea->setWidget(m_d->wdgProperties);
    layout->addWidget(m_d->wdgPropertiesArea);

    // unfortunately the sizeHint() function of QScrollArea is pretty broken
    // and it would add another event loop iteration to react to it anyway,
    // so let's just catch LayoutRequest events from the properties widget directly
    m_d->wdgProperties->installEventFilter(this);

    updateIcons();

    setCursor(Qt::ArrowCursor);

    // Prevent tablet events from being captured by the canvas
    setAttribute(Qt::WA_NoMousePropagation, true);
}



KisBrushHud::~KisBrushHud()
{
}

void KisBrushHud::updateIcons()
{
    this->setPalette(qApp->palette());
    for(int i=0; i<this->children().size(); i++) {
        QWidget *w = qobject_cast<QWidget*>(this->children().at(i));
        if (w) {
            w->setPalette(qApp->palette());
        }
    }
    for(int i=0; i<m_d->wdgProperties->children().size(); i++) {
        KisUniformPaintOpPropertyWidget *w = qobject_cast<KisUniformPaintOpPropertyWidget*>(m_d->wdgProperties->children().at(i));
        if (w) {
            w->slotThemeChanged(qApp->palette());
        }
    }
    m_d->btnReloadPreset->setIcon(KisIconUtils::loadIcon("reload-preset-16"));
    m_d->btnConfigure->setIcon(KisIconUtils::loadIcon("applications-system"));
}

void KisBrushHud::slotReloadProperties()
{
    m_d->presetConnections.clear();
    clearProperties();
    updateProperties();
}

void KisBrushHud::clearProperties() const
{
    while (m_d->propertiesLayout->count()) {
        QLayoutItem *item = m_d->propertiesLayout->takeAt(0);

        QWidget *w = item->widget();
        if (w) {
            w->deleteLater();
        }

        delete item;
    }

    m_d->currentPreset.clear();
}

void KisBrushHud::updateProperties()
{
    KisPaintOpPresetSP preset = m_d->provider->currentPreset();

    if (preset == m_d->currentPreset) return;

    m_d->presetConnections.clear();
    clearProperties();

    m_d->currentPreset = preset;
    m_d->presetConnections.addConnection(
        m_d->currentPreset->updateProxy(), SIGNAL(sigUniformPropertiesChanged()),
        this, SLOT(slotReloadProperties()));

    m_d->lblPresetIcon->setPixmap(QPixmap::fromImage(preset->image()));
    m_d->lblPresetName->setLongText(preset->name());

    QList<KisUniformPaintOpPropertySP> properties;

    {
        QList<KisUniformPaintOpPropertySP> allProperties = preset->uniformProperties();
        QList<KisUniformPaintOpPropertySP> discardedProperties;

        KisBrushHudPropertiesConfig cfg;
        cfg.filterProperties(preset->paintOp().id(),
                             allProperties,
                             &properties,
                             &discardedProperties);
    }

    Q_FOREACH(auto property, properties) {
        QWidget *w = 0;

        if (!property->isVisible()) continue;

        if (property->type() == KisUniformPaintOpProperty::Int) {
            w = new KisUniformPaintOpPropertyIntSlider(property, m_d->wdgProperties);
        } else if (property->type() == KisUniformPaintOpProperty::Double) {
            w = new KisUniformPaintOpPropertyDoubleSlider(property, m_d->wdgProperties);
        } else if (property->type() == KisUniformPaintOpProperty::Bool) {
            w = new KisUniformPaintOpPropertyCheckBox(property, m_d->wdgProperties);
        } else if (property->type() == KisUniformPaintOpProperty::Combo) {
            w = new KisUniformPaintOpPropertyComboBox(property, m_d->wdgProperties);
        }

        if (w) {
            w->setSizePolicy(QSizePolicy::MinimumExpanding, QSizePolicy::Fixed);
            m_d->propertiesLayout->addWidget(w);
        }
    }

    // Add tool-level widgets (like Snap to Assistants)
    updateToolOptionWidgets();
    if (!m_d->snapToAssistantsCheckbox.isNull()) {
        m_d->propertiesLayout->addWidget(m_d->snapToAssistantsCheckbox);
    }

    m_d->propertiesLayout->addStretch();
}

void KisBrushHud::showEvent(QShowEvent *event)
{
    m_d->connections.clear();
    m_d->connections.addUniqueConnection(
        m_d->provider->resourceManager(), SIGNAL(canvasResourceChanged(int,QVariant)),
        this, SLOT(slotCanvasResourceChanged(int,QVariant)));

    updateProperties();

    QWidget::showEvent(event);
}

void KisBrushHud::hideEvent(QHideEvent *event)
{
    m_d->connections.clear();
    QWidget::hideEvent(event);

    clearProperties();
}

void KisBrushHud::slotCanvasResourceChanged(int key, const QVariant &resource)
{
    Q_UNUSED(resource);

    if (key == KoCanvasResource::CurrentPaintOpPreset) {
        updateProperties();
    }
}

void KisBrushHud::paintEvent(QPaintEvent *event)
{
    QColor bgColor = palette().color(QPalette::Window);

    QPainter painter(this);
    painter.fillRect(rect() & event->rect(), bgColor);
    painter.end();

    QWidget::paintEvent(event);
}

bool KisBrushHud::event(QEvent *event)
{
    switch (event->type()) {
    case QEvent::TabletPress:
    case QEvent::TabletMove:
    case QEvent::TabletRelease:
        // Allow the tablet event to be translated to a mouse event on certain platforms
        break;
    case QEvent::MouseButtonPress:
    case QEvent::MouseMove:
    case QEvent::MouseButtonRelease:
    case QEvent::Wheel:
        event->accept();
        return true;
    default:
        break;
    }

    return QWidget::event(event);
}

bool KisBrushHud::eventFilter(QObject *watched, QEvent *event)
{
    // LayoutRequest event is sent from a layout to its parent widget
    // when size requirements have been determined, i.e. sizeHint is available
    if (watched == m_d->wdgProperties && event->type() == QEvent::LayoutRequest)
    {
        int totalMargin = 2 * m_d->wdgPropertiesArea->frameWidth();
        m_d->wdgPropertiesArea->setMinimumWidth(m_d->wdgProperties->sizeHint().width() + totalMargin);
    }
    return false;
}

void KisBrushHud::slotConfigBrushHud()
{
    if (!m_d->currentPreset) return;

    KisDlgConfigureBrushHud dlg(m_d->currentPreset);
    dlg.exec();

    slotReloadProperties();
}

void KisBrushHud::slotReloadPreset()
{
    KisCanvas2* canvas = dynamic_cast<KisCanvas2*>(m_d->provider->canvas());
    KIS_ASSERT_RECOVER_RETURN(canvas);
    canvas->viewManager()->actionCollection()->action("reload_preset_action")->trigger();
}

QCheckBox* KisBrushHud::findSnapToAssistantsCheckBox()
{
    // Search for a checkbox with the text "Snap to Assistants" in the stored tool option widgets
    for (QPointer<QWidget> widget : m_d->toolOptionWidgets) {
        if (!widget.isNull()) {
            QCheckBox *checkbox = qobject_cast<QCheckBox*>(widget.data());
            if (checkbox && checkbox->text() == i18n("Snap to Assistants")) {
                return checkbox;
            }

            // Also search children in case the checkbox is nested
            QList<QCheckBox*> checkboxes = widget->findChildren<QCheckBox*>();
            for (QCheckBox *checkbox : checkboxes) {
                if (checkbox->text() == i18n("Snap to Assistants")) {
                    return checkbox;
                }
            }
        }
    }

    return nullptr;
}

void KisBrushHud::setToolOptionWidgets(const QList<QPointer<QWidget>> &widgets)
{
    m_d->toolOptionWidgets = widgets;
    // Refresh the tool option widgets display if we have a current preset
    if (m_d->currentPreset && m_d->propertiesLayout) {
        updateToolOptionWidgets();
        if (!m_d->snapToAssistantsCheckbox.isNull()) {
            // Remove and re-add to ensure proper positioning (before the stretch)
            m_d->propertiesLayout->removeWidget(m_d->snapToAssistantsCheckbox);
            m_d->propertiesLayout->insertWidget(m_d->propertiesLayout->count() - 1, m_d->snapToAssistantsCheckbox);
        }
    }
}

void KisBrushHud::updateToolOptionWidgets()
{
    // Clean up previous tool option widgets from our layout
    if (!m_d->snapToAssistantsCheckbox.isNull()) {
        m_d->propertiesLayout->removeWidget(m_d->snapToAssistantsCheckbox);
        // Properly delete the checkbox to prevent it from becoming an orphaned top-level window
        m_d->snapToAssistantsCheckbox->deleteLater();
        m_d->snapToAssistantsCheckbox = nullptr;
    }

    // Check config to see if Snap to Assistants should be shown
    if (m_d->currentPreset) {
        KisBrushHudPropertiesConfig cfg;
        QList<QString> selectedIds = cfg.selectedProperties(m_d->currentPreset->paintOp().id());
        const QString snapToAssistantsId = "tool://snap_to_assistants";
        m_d->showSnapToAssistants = selectedIds.contains(snapToAssistantsId);
    }

    // Check if we should show the Snap to Assistants option
    if (!m_d->showSnapToAssistants) {
        return;
    }

    // Try to find the Snap to Assistants checkbox from the tool
    QCheckBox *originalCheckbox = findSnapToAssistantsCheckBox();
    if (originalCheckbox) {
        // Create our own checkbox that mirrors the original
        m_d->snapToAssistantsCheckbox = new QCheckBox(m_d->wdgProperties);
        m_d->snapToAssistantsCheckbox->setText(i18n("Snap to Assistants"));
        m_d->snapToAssistantsCheckbox->setChecked(originalCheckbox->isChecked());

        // Connect the two checkboxes to stay in sync
        connect(m_d->snapToAssistantsCheckbox, &QCheckBox::toggled, originalCheckbox, &QCheckBox::setChecked);
        connect(originalCheckbox, &QCheckBox::toggled, m_d->snapToAssistantsCheckbox.data(), &QCheckBox::setChecked);

        m_d->snapToAssistantsCheckbox->setSizePolicy(QSizePolicy::MinimumExpanding, QSizePolicy::Fixed);
    }
}
