#!/bin/sh

echo

# Remove "$NEWROOT"/.successful-update if exists
rm -f "$NEWROOT"/.successful-update "$NEWROOT"/.update

# Detect if update downloaded.
if [ -d "$NEWROOT"/.update_rootfs ]; then
    # Available, rename old /usr and move new /usr to /.
    if [ -d "$NEWROOT"/.update_rootfs/usr ]; then
        rm -rf "$NEWROOT"/.old.usr
        mv "$NEWROOT"/usr "$NEWROOT"/.old.usr >/dev/null 2>&1
        mv "$NEWROOT"/.update_rootfs/usr "$NEWROOT"/usr
    fi

    # Same for /etc.
    if [ -d "$NEWROOT"/.update_rootfs/etc ]; then
        mv "$NEWROOT"/.update_rootfs/etc "$NEWROOT"/usr/etc
    fi
    if [ -d "$NEWROOT"/.new.etc ]; then
        rm -rf "$NEWROOT"/.old.etc
        mv "$NEWROOT"/etc "$NEWROOT"/.old.etc >/dev/null 2>&1
        mv "$NEWROOT"/.new.etc "$NEWROOT"/etc
    fi

    # Same for /var.
    if [ -d "$NEWROOT"/.new.var.lib ]; then
        rm -rf "$NEWROOT"/.old.var.lib
        mv "$NEWROOT"/var/lib "$NEWROOT"/.old.var.lib >/dev/null 2>&1
        mv "$NEWROOT"/.new.var.lib "$NEWROOT"/var/lib
    fi
    if [ -d "$NEWROOT"/.update_rootfs/var/cache/pacman ]; then
        rm -rf "$NEWROOT"/.old.var.cache.pacman
        mv "$NEWROOT"/var/cache/pacman "$NEWROOT"/.old.var.cache.pacman >/dev/null 2>&1
        mv "$NEWROOT"/.update_rootfs/var/cache/pacman "$NEWROOT"/var/cache/pacman
    fi

    rm -rf "$NEWROOT"/.old.update_rootfs
    mv "$NEWROOT"/.update_rootfs "$NEWROOT"/.old.update_rootfs
    touch "$NEWROOT"/.successful-update
fi

for i in usr varlibpacman usrlocal; do
    rm -rf "$NEWROOT"/.commonarch-overlays/$i.workdir
    mkdir -p "$NEWROOT"/.commonarch-overlays/$i
    mkdir -p "$NEWROOT"/.commonarch-overlays/$i.workdir
done

mount -t overlay overlay -o index=off -o metacopy=off -o ro,lowerdir="$NEWROOT"/usr,upperdir="$NEWROOT"/.commonarch-overlays/usr,workdir="$NEWROOT"/.commonarch-overlays/usr.workdir "$NEWROOT"/usr
mount -t overlay overlay -o index=off -o metacopy=off -o ro,lowerdir="$NEWROOT"/var/lib/pacman,upperdir="$NEWROOT"/.commonarch-overlays/varlibpacman,workdir="$NEWROOT"/.commonarch-overlays/varlibpacman.workdir "$NEWROOT"/var/lib/pacman
mount -t overlay overlay -o rw,lowerdir="$NEWROOT"/usr/local,upperdir="$NEWROOT"/.commonarch-overlays/usrlocal,workdir="$NEWROOT"/.commonarch-overlays/usrlocal.workdir "$NEWROOT"/usr/local
