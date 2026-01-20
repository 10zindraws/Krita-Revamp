/*
 * SPDX-FileCopyrightText: 2026 Tenzin Rangdol tenzindraws@gmail.com
 *
 * SPDX-License-Identifier: LGPL-2.0-or-later
 */

#ifndef KISPRESETORDERMANAGER_H
#define KISPRESETORDERMANAGER_H

#include <QObject>
#include <QMap>
#include <QList>
#include <QString>
#include <QMutex>

#include "kritaresources_export.h"

/**
 * @brief The KisPresetOrderManager class manages custom ordering of brush presets per tag.
 *
 * This singleton class stores the user-defined order of brush presets within each tag.
 * The order is persisted to a JSON config file and loaded on startup.
 *
 * Key behaviors:
 * - New presets are added at the top of the list (position 0)
 * - Multiple new presets are ordered alphanumerically among themselves at the top
 * - User can drag-reorder presets to any position
 * - Order is stored per tag (including "All" and "Untagged")
 */
class KRITARESOURCES_EXPORT KisPresetOrderManager : public QObject
{
    Q_OBJECT

public:
    static KisPresetOrderManager *instance();
    ~KisPresetOrderManager() override;

    /**
     * @brief getOrderForTag Get the ordered list of resource IDs for a tag
     * @param tagUrl The tag URL (use empty string for "All")
     * @return List of resource IDs in display order
     */
    QList<int> getOrderForTag(const QString &tagUrl) const;

    /**
     * @brief setOrderForTag Set the complete order for a tag
     * @param tagUrl The tag URL
     * @param resourceIds List of resource IDs in desired order
     */
    void setOrderForTag(const QString &tagUrl, const QList<int> &resourceIds);

    /**
     * @brief getPosition Get the display position for a resource in a tag
     * @param tagUrl The tag URL
     * @param resourceId The resource ID
     * @return Position (0-based), or -1 if not found (new resource)
     */
    int getPosition(const QString &tagUrl, int resourceId) const;

    /**
     * @brief hasCustomOrder Check if a tag has custom ordering defined
     * @param tagUrl The tag URL
     * @return true if custom order exists
     */
    bool hasCustomOrder(const QString &tagUrl) const;

    /**
     * @brief moveResource Move a resource to a new position within a tag
     * @param tagUrl The tag URL
     * @param resourceId The resource to move
     * @param newPosition The target position (0-based)
     */
    void moveResource(const QString &tagUrl, int resourceId, int newPosition);

    /**
     * @brief moveResources Move multiple resources to a new position
     * @param tagUrl The tag URL
     * @param resourceIds Resources to move (in order)
     * @param targetPosition Target position for first resource
     */
    void moveResources(const QString &tagUrl, const QList<int> &resourceIds, int targetPosition);

    /**
     * @brief addNewResources Add new resources at the top, in alphanumeric order
     * @param tagUrl The tag URL
     * @param resourceIds New resource IDs
     * @param resourceNames Names for sorting (parallel list to resourceIds)
     */
    void addNewResources(const QString &tagUrl, const QList<int> &resourceIds, const QStringList &resourceNames);

    /**
     * @brief removeResource Remove a resource from the order (when untagged)
     * @param tagUrl The tag URL
     * @param resourceId The resource to remove
     */
    void removeResource(const QString &tagUrl, int resourceId);

    /**
     * @brief clearOrderForTag Clear custom order for a tag (revert to default)
     * @param tagUrl The tag URL
     */
    void clearOrderForTag(const QString &tagUrl);

    /**
     * @brief save Save all orders to disk
     */
    void save();

    /**
     * @brief load Load orders from disk
     */
    void load();

Q_SIGNALS:
    /**
     * @brief orderChanged Emitted when order changes for a tag
     * @param tagUrl The tag that changed
     */
    void orderChanged(const QString &tagUrl);

private:
    KisPresetOrderManager();
    KisPresetOrderManager(const KisPresetOrderManager &) = delete;
    KisPresetOrderManager &operator=(const KisPresetOrderManager &) = delete;

    QString configFilePath() const;

    static KisPresetOrderManager *s_instance;
    static QMutex s_instanceMutex;

    struct Private;
    Private *const d;
};

#endif // KISPRESETORDERMANAGER_H
