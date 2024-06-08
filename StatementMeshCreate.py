"""
Purpose:  電子化データ用の細分メッシュ作成
Author:   長谷川 直希
Created:  2023/08/02
Update:   2024/04/02

◆内容
    3次メッシュを25mか5mメッシュに分割し、電子化データ用メッシュコード & 緯度経度を追加
◆使い方
    1、3次メッシュをGISPROに入れる
        ※必要テーブル ⇒ 3次メッシュID(例:55392700)
        ※必要な3次メッシュのみで動作します(長方形でなく、穴あき形状でも動作します)
    2、下記変数を入力
    3、GISProのPythonにコードを貼付けEnterで実行
◆注意点
    ・マップ座標系と3次メッシュを同じ地理座標系に設定してください（平面直角座標系はエラーになります）
        OK = 日本測地系2000(JGD2000)
        NG = 平面直角座標系 第9系(JGD2000)
            ※マップと3次メッシュでJGD2000,JGD2011も一致させてください（違うと位置がずれます）"""
import os
import time
import arcpy

#==変数の入力=================================================
mesh_name_3r = "Mesh3_JGD2011_抜粋"  # レイヤ名：3次メッシュ
id_name_3r = "MESH3_ID"  # フィールド名：3次メッシュID
mesh_size =  25 # 作成メッシュの選択：[25mMESH = 25, 5mMESH = 5]

# shp：保存先
output_path = r"C:\Users\KASEN-NILIM14\Desktop\work\GISpro\マイ プロジェクト\shp\mesh"

# マージ：有無（3次メッシュ毎の分割メッシュ）
is_split_mesh_merge = False # [True = マージする、False = マージなし]
#============================================================

# オブジェクト取得(プロジェクト)
aprx = arcpy.mp.ArcGISProject("CURRENT") 
# オブジェクト取得(マップ)
map = aprx.listMaps()[0]
# リスト初期化(分割メッシュ名)
split_mesh_list = []
# 開始時間(計測用)
start_time = time.time()


def main():
    """メインの処理（使う関数を集約して順番に並べてます）"""

    countup = 0
    clear_select_layer() # 選択解除
    x_max, y_max = mesh_split_number() # 分割数の取得
    cursor =  arcpy.da.SearchCursor(mesh_name_3r, id_name_3r) # カーソル作成
    
    # 3次メッシュのテーブル数でループ
    for row in cursor:
        countup += 1
        mesh3_ID = str(row[0]) # 3次メッシュID取得
        print(str(countup) + " :3次メッシュID " + mesh3_ID + "の処理中...")

        # 3次メッシュ保存(1メッシュ)
        one_mesh3_export(mesh3_ID) 
        
        # メッシュ分割
        split_mesh = split_mesh_make(mesh3_ID, x_max, y_max) 

        # XYの入力
        xy_add(split_mesh, x_max, y_max)
        
        # メッシュコード用YXの入力
        meshcode_yx_add(split_mesh, mesh_size)

        # メッシュコード作成（3Rコード + 指示符 + YX）
        join_after_mesh = split_mesh + r"_MeshCodeAdd"
        meshcode_join_create(split_mesh, mesh_name_3r, output_path, mesh_size, id_name_3r, join_after_mesh)

        # メッシュ4隅の緯度経度を取得
        xy_coordinates_txt_output(join_after_mesh, output_path)

        # メッシュに緯度経度を入力
        xy_add_table(join_after_mesh, output_path)
        
        # 経過ファイル削除(レイヤオブジェクト)
        split_mesh_name = join_after_mesh + r"_xy"
        lyrer_remove(split_mesh_name)

        # 経過ファイル完全削除(シェープファイル)
        shape_delete(mesh3_ID)
        shape_delete(split_mesh)

        # リスト作成(分割メッシュのマージ用)
        split_mesh_list.append(split_mesh_name + ".shp")
    
    # 選択解除
    clear_select_layer()

    # メッシュのマージ(3次メッシュ毎の分割メッシュを統合)
    if is_split_mesh_merge == True:
        # 分割メッシュのマージ
        mesh_merge(split_mesh_list)

        # ファイルの完全削除(3次メッシュ毎の分割メッシュ)
        one_split_mesh_delete()
    
    print(">>完了!<<")


def mesh_split_number():
    """メッシュ分割数を取得"""
    if mesh_size == 25:
        x_max = 40 #メッシュ列数
        y_max = 40 #メッシュ行数
    elif mesh_size == 5:
        x_max = 200 #メッシュ列数
        y_max = 200 #メッシュ行数
    
    print(str(mesh_size) + r"mメッシュの作成")
    print("メッシュ分割数 列：" + str(x_max) + " 行：" + str(y_max) + "\n")

    return x_max, y_max


def one_mesh3_export(mesh3_ID):
    """
    3次メッシュを保存(1メッシュのみ)

    Args:
        mesh3_ID (str): フィールド名(メッシュID)
    """
    # 3次メッシュ1つ選択
    expression = "{} = {}".format(id_name_3r, mesh3_ID) #SQL式
    arcpy.SelectLayerByAttribute_management(mesh_name_3r, "NEW_SELECTION", expression)

    # 選択フィーチャ保存
    output_filename = mesh3_ID + ".shp"
    arcpy.FeatureClassToFeatureClass_conversion(mesh_name_3r, output_path, output_filename)


def split_mesh_make(mesh3_ID, x_max, y_max):
    """
    メッシュ分割

    Args:
        mesh3_ID (str): フィールド名(メッシュID)
        x_max (int): 分割数(X方向)
        y_max (int): 分割数(Y方向)

    Returns:
        str: レイヤ名(3次メッシュID + メッシュサイズ)
    """
    print(mesh3_ID + "の分割中...")
    split_mesh = mesh3_ID + "_" + str(mesh_size) + "m"
    output_mesh_name = output_path + "\\" + split_mesh + ".shp"
    
    # メッシュの分割
    arcpy.GridIndexFeatures_cartography(output_mesh_name, mesh3_ID, "INTERSECTFEATURE",
                                        "#","#","#","#","#", y_max, x_max, "1", "LABELFROMORIGIN")
    
    # 不要なフィールド削除（PageName）
    arcpy.management.DeleteField(split_mesh, "PageName", "DELETE_FIELDS")

    # 経過時間を出力
    print(processing_time(start_time))

    return split_mesh


def xy_add(in_layer, x_max, y_max):
    """
    XYの入力

    Args:
        in_layer (str): レイヤ名(3次メッシュID + メッシュサイズ)
        x_max (int): 分割数(X方向)
        y_max (int): 分割数(Y方向)
    """    
    print("XYを入力中...")
    name_x = "X"
    name_y = "Y"
    selection_type = "NEW_SELECTION"
    
    # フィールド追加
    arcpy.management.AddField(in_layer, name_x, "SHORT", 4, None, 16, '', "NULLABLE", "NON_REQUIRED", '')
    arcpy.management.AddField(in_layer, name_y, "SHORT", 4, None, 16, '', "NULLABLE", "NON_REQUIRED", '')
    
    # Xを入力
    arcpy.management.CalculateField(in_layer, name_x, '!PageNumber! % ' + str(x_max), "PYTHON3")
    where_clause = 'X = 0'
    arcpy.SelectLayerByAttribute_management (in_layer, selection_type, where_clause)
    arcpy.management.CalculateField(in_layer, name_x, x_max, "PYTHON3")
    arcpy.SelectLayerByAttribute_management(in_layer,"CLEAR_SELECTION")

    # Yを入力
    arcpy.management.CalculateField(in_layer, name_y, 'int(!PageNumber! / ' + str(x_max) + ')', "PYTHON3")
    arcpy.management.CalculateField(in_layer, name_y,  '!Y! + 1', "PYTHON3")
    where_clause = 'X = ' + str(x_max)
    arcpy.SelectLayerByAttribute_management (in_layer, selection_type, where_clause)
    arcpy.management.CalculateField(in_layer, name_y,  '!Y! - 1', "PYTHON3")
    arcpy.SelectLayerByAttribute_management(in_layer,"CLEAR_SELECTION")

    
    # 経過時間を出力
    print(processing_time(start_time))


def meshcode_yx_add(in_layer, mesh_size):
    """
    メッシュコード用YXの入力

    Args:
        in_layer (str): レイヤ名
        mesh_size (int): メッシュサイズ
    """
    print("MESHCODE用のYX入力中...")

    # フィールド追加
    field_name = "CodeYX"
    arcpy.management.AddField(in_layer, field_name, "TEXT", None, None, 16, '', "NULLABLE", "NON_REQUIRED", '')

    # フィールド演算
    if mesh_size == 25:
        arcpy.management.CalculateField(in_layer, field_name,'"{0:02}".format(( !Y! -1) % 40) + "{0:02}".format(( !X! ! -1) % 40)',
                                        "PYTHON3", '', "TEXT", "NO_ENFORCE_DOMAINS")
    elif mesh_size == 5:
        arcpy.management.CalculateField(in_layer, field_name, '"{0:03}".format(( !Y! -1) % 200) + "{0:03}".format(( !X! ! -1) % 200)',
                                        "PYTHON3", '', "TEXT", "NO_ENFORCE_DOMAINS")

    # 不要なフィールド削除（メッシュコード入力後にX,Yは不要なため）
    arcpy.management.DeleteField(in_layer, "X;Y", "DELETE_FIELDS")
    
    # 経過時間を出力
    print(processing_time(start_time))


def meshcode_join_create(division_mesh, basis_mesh, output_path, mesh_size, id_name_3r, after_mesh):
    """
    メッシュコード作成（3Rコード + 指示符 + YX）

    Args:
        division_mesh (str): レイヤ名(3次メッシュID + メッシュサイズ)
        basis_mesh (int): レイヤ名：3次メッシュ
        output_path (str): 保存先
        mesh_size (int): メッシュサイズ
        id_name_3r (int): フィールド名(3次メッシュID)
        after_mesh (str): レイヤ名(3次メッシュID + メッシュサイズ + "_MeshCodeAdd")
    """
    print("MESHCODEを作成中...")
    join_after_mesh = after_mesh

    # 3Rメッシュを空間結合(重心)
    arcpy.analysis.SpatialJoin(division_mesh, basis_mesh, output_path + r"\\" + join_after_mesh, "", "", "", "HAVE_THEIR_CENTER_IN")

    # フィールド追加
    arcpy.management.AddField(join_after_mesh, "MESHCODE", "TEXT", None, None, 16, '', "NULLABLE", "NON_REQUIRED", '')    

    if mesh_size == 25:
        split_sign_number = str(3)
    elif mesh_size == 5:
        split_sign_number = str(2)
    
    # フィールド演算
    code_name = "str(!" + id_name_3r + "!) +str(" + split_sign_number  +  ")+ str(!CodeYX!)"
    arcpy.management.CalculateField(join_after_mesh, "MESHCODE", code_name, "PYTHON3", '', "TEXT", "NO_ENFORCE_DOMAINS")
    
    # 不要なフィールド削除
    delete_field_name = "Join_Count;TARGET_FID;CodeYX" + ";" + id_name_3r
    arcpy.management.DeleteField(join_after_mesh, delete_field_name, "DELETE_FIELDS")
    
    # 経過時間を出力
    print(processing_time(start_time))


def xy_coordinates_txt_output(infc, output_path):
    """
    メッシュ4隅の緯度経度を取得

    Args:
        infc (str): レイヤ名(3次メッシュID + メッシュサイズ + "_MeshCodeAdd")
        output_path (str): 保存先
    """
    print("メッシュ4隅の緯度経度を取得中...")
    f = open(output_path + r"\output_XY.txt", "w")
    
    # ジオメトリを格納するフィールド名を取得
    desc = arcpy.Describe(infc)
    shapefieldname = desc.shapeFieldName
    
    # サーチカーソルの作成
    rows = arcpy.SearchCursor(infc)
    header_name = "PNo,左下経,左下緯,右下経,右下緯,右上経,右上緯,左上経,左上緯"
    f.write(header_name)

    # すべてのフィーチャ（または行）に対してループで実行
    for row in rows:
        # フィーチャ（または行）の座標値を取得する
        feat = row.getValue(shapefieldname)

        # フィーチャID
        page_number = str(row.getValue(desc.OIDFieldName) + 1)
        partnum = 0 # パート番号をリセット
    
        # フィーチャのパートごとの処理
        for part in feat:
            pnt_count = 0

            # パートに含まれるポイントをファイルに出力する
            for pnt in feat.getPart(partnum):
                pnt_count += 1

                if pnt:
                    # ポイントのX座標とY座標を出力用文字列に代入
                    if pnt_count == 1: P1X, P1Y = str(pnt.X), str(pnt.Y)
                    if pnt_count == 2: P4X, P4Y = str(pnt.X), str(pnt.Y)
                    if pnt_count == 3: P3X, P3Y = str(pnt.X), str(pnt.Y)
                    if pnt_count == 4: P2X, P2Y = str(pnt.X), str(pnt.Y)
                    if pnt_count > 4: pass
                else:
                    partnum += 1
            partnum += 1
            output_str = page_number + "," + P1X + "," + P1Y + "," + P2X + "," + P2Y + "," + P3X + "," + P3Y + "," + P4X + "," + P4Y
            f.write("\n" + output_str)

    del row, rows # オブジェクトの参照解放
    f.close() # ファイルを閉じる

    # 経過時間を出力
    print(processing_time(start_time))


def xy_add_table(split_mesh, output_path):
    """
    メッシュに緯度経度を入力

    Args:
        split_mesh (str): レイヤ名(3次メッシュID + メッシュサイズ + "_MeshCodeAdd")
        output_path (str): 保存先
    """
    print("メッシュに緯度経度を入力中...")
    txt_data = output_path + r"\output_XY.txt"
    
    # テーブル結合
    arcpy.management.AddJoin(split_mesh, "PageNumber", txt_data, "PNo", "KEEP_ALL", "NO_INDEX_JOIN_FIELDS")
    
    # メッシュを保存
    xy_mesh_name = split_mesh + r"_xy"
    arcpy.conversion.FeatureClassToFeatureClass(split_mesh, output_path, xy_mesh_name)
    
    # フィールドの削除
    arcpy.management.DeleteField(xy_mesh_name, "PNo", "DELETE_FIELDS")
    arcpy.management.DeleteField(xy_mesh_name, "PageNumber", "DELETE_FIELDS")
    
    # 不要shpの完全削除
    shape_delete(split_mesh)

    # 出力したTXTファイルを削除
    os.remove(output_path + r"\output_XY.txt")

    # 経過時間を出力
    print(processing_time(start_time))


def lyrer_remove(lyrer_name):
    """
    レイヤをマップから削除

    Args:
        lyrer_name (str): レイヤ名
    """
    layer = map.listLayers(lyrer_name)[0] # レイヤーオブジェクト取得
    map.removeLayer(layer) # レイヤーオブジェクト削除


def clear_select_layer():
    """選択解除"""
    arcpy.SelectLayerByAttribute_management(mesh_name_3r, "CLEAR_SELECTION")


def mesh_merge(output_mesh_list):
    """
    メッシュのマージ(3次メッシュ毎の分割メッシュ統合)

    Args:
        output_mesh_list (list): shp名(分割メッシュ名のリスト)
    """
    print(str(mesh_size) + "mメッシュをマージ中...")
    
    # リスト内の要素をセミコロンで連結
    marge_names_str = ";".join(output_mesh_list)
    
    # ワークスペースをshp保存先に指定
    arcpy.env.workspace = output_path

    # マージ
    arcpy.management.Merge(marge_names_str, output_path + "\\" + str(mesh_size) + r"m_MESH.shp")

    # 経過時間を出力
    print(processing_time(start_time))


def one_split_mesh_delete():
    """ファイル完全削除(3次メッシュ毎の分割shp)"""

    print("3次メッシュ毎の分割後メッシュの削除中...")

    for delete_mesh in split_mesh_list:
        delete_mesh_name = delete_mesh.replace(".shp", "") #文字列から.shpを削除
        shape_delete(delete_mesh_name)
    
    # 経過時間を出力
    print(processing_time(start_time))


def processing_time(start_time):
    """経過時間を算出"""

    end = time.time() - start_time
    processing_time_str = " -処理時間" + str(round(end,1)) + "秒-" + "\n"
    return processing_time_str


def shape_delete(shape_name):
    """shpの完全削除"""
    arcpy.management.Delete(output_path + "\\" + shape_name + ".shp")


if __name__ == "__main__":
    main()
