package org.syun.pokemonw2

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import android.os.ParcelFileDescriptor
import java.io.File
import java.io.FileNotFoundException

class GameProvider : ContentProvider() {
    override fun onCreate(): Boolean = true

    override fun getType(uri: Uri): String = MIME_TYPE

    override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor {
        if (mode != "r") throw FileNotFoundException("The game image is read-only")
        val image = checkedImage(uri)
        return ParcelFileDescriptor.open(image, ParcelFileDescriptor.MODE_READ_ONLY)
    }

    override fun query(
        uri: Uri,
        projection: Array<out String>?,
        selection: String?,
        selectionArgs: Array<out String>?,
        sortOrder: String?,
    ): Cursor {
        val image = checkedImage(uri)
        val requested = projection?.toList() ?: DEFAULT_COLUMNS
        val cursor = MatrixCursor(requested.toTypedArray())
        cursor.addRow(requested.map { column ->
            when (column) {
                "_display_name" -> "Pokemon White 2.nds"
                "_size" -> image.length()
                "mime_type" -> MIME_TYPE
                "flags" -> 0
                "document_id" -> FILE_NAME
                "last_modified" -> image.lastModified()
                "_id" -> 1
                else -> null
            }
        })
        return cursor
    }

    override fun insert(uri: Uri, values: ContentValues?): Uri? = null

    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0

    override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?): Int = 0

    private fun checkedImage(uri: Uri): File {
        if (uri.path != "/$FILE_NAME") throw FileNotFoundException("Unknown game URI")
        val image = File(requireNotNull(context).filesDir, FILE_NAME)
        if (!image.isFile || image.length() != EXPECTED_SIZE) throw FileNotFoundException("The game image is not ready")
        return image
    }

    companion object {
        const val FILE_NAME = "pokemon_white2.nds"
        const val MIME_TYPE = "application/x-nintendo-ds-rom"
        private const val EXPECTED_SIZE = 536_870_912L
        private val DEFAULT_COLUMNS = listOf("_display_name", "_size", "mime_type", "flags", "document_id", "last_modified", "_id")
    }
}
