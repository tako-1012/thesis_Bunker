using UnityEngine;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Collections.Generic;
using System;

/// <summary>
/// Unity側のROS2地形データ受信スクリプト
/// TCP/IP経由でROS2から地形解析データを受信し、Unity内で可視化する
/// </summary>
public class TerrainDataReceiver : MonoBehaviour
{
    [Header("Connection Settings")]
    public string serverHost = "127.0.0.1";
    public int serverPort = 10000;
    public float reconnectInterval = 5.0f;
    
    [Header("Visualization Settings")]
    public GameObject voxelPrefab;
    public Material[] terrainMaterials; // 0:平坦, 1:緩傾斜, 2:中傾斜, 3:急傾斜, 4:障害物
    public Transform terrainParent;
    
    [Header("Debug")]
    public bool enableDebugLog = true;
    public bool showConnectionStatus = true;
    
    // ネットワーク関連
    private TcpClient client;
    private NetworkStream stream;
    private Thread receiveThread;
    private bool isConnected = false;
    private bool shouldReconnect = true;
    
    // データ管理
    private Queue<string> messageQueue = new Queue<string>();
    private object queueLock = new object();
    
    // 地形データ
    private TerrainData currentTerrainData;
    private List<GameObject> voxelObjects = new List<GameObject>();
    
    // 統計情報
    private int messagesReceived = 0;
    private float lastMessageTime = 0f;
    
    void Start()
    {
        InitializeTerrainData();
        ConnectToROS();
    }
    
    void Update()
    {
        // メッセージキューからデータを処理
        ProcessMessageQueue();
        
        // 接続状態の表示
        if (showConnectionStatus)
        {
            UpdateConnectionStatus();
        }
        
        // 再接続処理
        if (!isConnected && shouldReconnect)
        {
            if (Time.time - lastMessageTime > reconnectInterval)
            {
                ConnectToROS();
            }
        }
    }
    
    void InitializeTerrainData()
    {
        currentTerrainData = new TerrainData();
        
        // 地形親オブジェクトの作成
        if (terrainParent == null)
        {
            GameObject terrainGO = new GameObject("TerrainData");
            terrainParent = terrainGO.transform;
        }
    }
    
    void ConnectToROS()
    {
        try
        {
            client = new TcpClient();
            client.Connect(serverHost, serverPort);
            stream = client.GetStream();
            
            isConnected = true;
            shouldReconnect = true;
            
            // 受信スレッド開始
            receiveThread = new Thread(ReceiveDataLoop);
            receiveThread.IsBackground = true;
            receiveThread.Start();
            
            LogDebug($"Connected to ROS2 Bridge at {serverHost}:{serverPort}");
            
        }
        catch (Exception e)
        {
            LogDebug($"Connection failed: {e.Message}");
            isConnected = false;
        }
    }
    
    void ReceiveDataLoop()
    {
        byte[] lengthBuffer = new byte[4];
        
        while (isConnected && client.Connected)
        {
            try
            {
                // データ長を読み取り
                int bytesRead = stream.Read(lengthBuffer, 0, 4);
                if (bytesRead != 4)
                {
                    break;
                }
                
                int dataLength = BitConverter.ToInt32(lengthBuffer, 0);
                if (dataLength <= 0 || dataLength > 1024 * 1024) // 1MB制限
                {
                    LogDebug($"Invalid data length: {dataLength}");
                    break;
                }
                
                // データ本体を読み取り
                byte[] dataBuffer = new byte[dataLength];
                int totalBytesRead = 0;
                
                while (totalBytesRead < dataLength)
                {
                    int bytesReadThisTime = stream.Read(dataBuffer, totalBytesRead, dataLength - totalBytesRead);
                    if (bytesReadThisTime == 0)
                    {
                        break;
                    }
                    totalBytesRead += bytesReadThisTime;
                }
                
                if (totalBytesRead == dataLength)
                {
                    string jsonData = Encoding.UTF8.GetString(dataBuffer);
                    
                    lock (queueLock)
                    {
                        messageQueue.Enqueue(jsonData);
                    }
                    
                    messagesReceived++;
                    lastMessageTime = Time.time;
                }
                
            }
            catch (Exception e)
            {
                LogDebug($"Receive error: {e.Message}");
                break;
            }
        }
        
        // 接続終了処理
        isConnected = false;
        LogDebug("Disconnected from ROS2 Bridge");
    }
    
    void ProcessMessageQueue()
    {
        lock (queueLock)
        {
            while (messageQueue.Count > 0)
            {
                string jsonData = messageQueue.Dequeue();
                ProcessTerrainData(jsonData);
            }
        }
    }
    
    void ProcessTerrainData(string json)
    {
        try
        {
            // JSON解析
            var data = JsonUtility.FromJson<TerrainMessage>(json);
            
            switch (data.message_type)
            {
                case "terrain_info":
                    ProcessTerrainInfo(data);
                    break;
                    
                case "voxel_grid":
                    ProcessVoxelGrid(data);
                    break;
                    
                case "unified_terrain":
                    ProcessUnifiedTerrain(data);
                    break;
                    
                case "status":
                    ProcessStatusMessage(data);
                    break;
                    
                default:
                    LogDebug($"Unknown message type: {data.message_type}");
                    break;
            }
        }
        catch (Exception e)
        {
            LogDebug($"JSON parsing error: {e.Message}");
        }
    }
    
    void ProcessTerrainInfo(TerrainMessage data)
    {
        // 地形統計情報の更新
        currentTerrainData.UpdateFromTerrainInfo(data);
        
        // UI更新（必要に応じて）
        UpdateTerrainUI();
        
        LogDebug($"Terrain Info: Avg Slope={data.statistics.avg_slope:F1}°, " +
                $"Traversable={data.statistics.traversable_ratio:P1}");
    }
    
    void ProcessVoxelGrid(TerrainMessage data)
    {
        // ボクセルデータの可視化
        VisualizeVoxels(data.voxel_samples);
        
        LogDebug($"Voxel Grid: {data.voxel_samples.Length} voxels");
    }
    
    void ProcessUnifiedTerrain(TerrainMessage data)
    {
        // 統合地形データの処理
        ProcessTerrainInfo(data);
        ProcessVoxelGrid(data);
    }
    
    void ProcessStatusMessage(TerrainMessage data)
    {
        LogDebug($"Status: {data.status} - {data.message}");
    }
    
    void VisualizeVoxels(VoxelSample[] voxels)
    {
        // 既存のボクセルオブジェクトを削除
        ClearVoxelObjects();
        
        if (voxels == null || voxelPrefab == null)
        {
            return;
        }
        
        // 新しいボクセルオブジェクトを作成
        foreach (var voxel in voxels)
        {
            GameObject voxelObj = Instantiate(voxelPrefab, terrainParent);
            
            // 位置設定
            Vector3 position = new Vector3(
                voxel.position.x * 0.1f, // ボクセルサイズを考慮
                voxel.position.y * 0.1f,
                voxel.position.z * 0.1f
            );
            voxelObj.transform.position = position;
            
            // マテリアル設定（傾斜に応じて）
            Renderer renderer = voxelObj.GetComponent<Renderer>();
            if (renderer != null && terrainMaterials != null)
            {
                int materialIndex = GetMaterialIndex(voxel.slope, voxel.type);
                if (materialIndex < terrainMaterials.Length)
                {
                    renderer.material = terrainMaterials[materialIndex];
                }
            }
            
            // スケール設定
            voxelObj.transform.localScale = Vector3.one * 0.1f; // ボクセルサイズ
            
            voxelObjects.Add(voxelObj);
        }
    }
    
    int GetMaterialIndex(float slope, int voxelType)
    {
        if (voxelType == 2) // 障害物
        {
            return 4; // 障害物マテリアル
        }
        
        // 傾斜に応じたマテリアル選択
        if (slope < 15f) return 0;      // 平坦
        if (slope < 25f) return 1;      // 緩傾斜
        if (slope < 35f) return 2;      // 中傾斜
        return 3;                       // 急傾斜
    }
    
    void ClearVoxelObjects()
    {
        foreach (var obj in voxelObjects)
        {
            if (obj != null)
            {
                DestroyImmediate(obj);
            }
        }
        voxelObjects.Clear();
    }
    
    void UpdateTerrainUI()
    {
        // UI更新処理（必要に応じて実装）
        // 例：スライダー、テキスト表示など
    }
    
    void UpdateConnectionStatus()
    {
        // 接続状態の表示（必要に応じて実装）
        // 例：UIテキスト、インジケーターなど
    }
    
    void LogDebug(string message)
    {
        if (enableDebugLog)
        {
            Debug.Log($"[TerrainDataReceiver] {message}");
        }
    }
    
    void OnDestroy()
    {
        // リソースのクリーンアップ
        shouldReconnect = false;
        isConnected = false;
        
        if (receiveThread != null && receiveThread.IsAlive)
        {
            receiveThread.Join(1000); // 1秒待機
        }
        
        if (stream != null)
        {
            stream.Close();
        }
        
        if (client != null)
        {
            client.Close();
        }
        
        ClearVoxelObjects();
    }
    
    void OnApplicationQuit()
    {
        OnDestroy();
    }
}

/// <summary>
/// 地形データクラス
/// </summary>
[System.Serializable]
public class TerrainData
{
    public float avgSlope;
    public float maxSlope;
    public float traversableRatio;
    public int totalVoxels;
    public int groundVoxels;
    public int obstacleVoxels;
    public float avgRisk;
    public float maxRisk;
    
    public void UpdateFromTerrainInfo(TerrainMessage data)
    {
        if (data.statistics != null)
        {
            avgSlope = data.statistics.avg_slope;
            maxSlope = data.statistics.max_slope;
            traversableRatio = data.statistics.traversable_ratio;
        }
        
        if (data.voxels != null)
        {
            totalVoxels = data.voxels.total;
            groundVoxels = data.voxels.ground;
            obstacleVoxels = data.voxels.obstacle;
        }
        
        if (data.risk != null)
        {
            avgRisk = data.risk.avg_score;
            maxRisk = data.risk.max_score;
        }
    }
}

/// <summary>
/// ROS2メッセージのJSON構造（Unity用）
/// </summary>
[System.Serializable]
public class TerrainMessage
{
    public string message_type;
    public float timestamp;
    public string frame_id;
    public TerrainStatistics statistics;
    public VoxelInfo voxels;
    public RiskInfo risk;
    public CostInfo cost;
    public PerformanceInfo performance;
    public VoxelSample[] voxel_samples;
    public string status;
    public string message;
}

[System.Serializable]
public class TerrainStatistics
{
    public float avg_slope;
    public float max_slope;
    public float min_slope;
    public float traversable_ratio;
}

[System.Serializable]
public class VoxelInfo
{
    public int total;
    public int ground;
    public int obstacle;
}

[System.Serializable]
public class RiskInfo
{
    public float avg_score;
    public float max_score;
}

[System.Serializable]
public class CostInfo
{
    public float avg_cost;
    public float impassable_ratio;
}

[System.Serializable]
public class PerformanceInfo
{
    public float processing_time;
    public int point_count;
}

[System.Serializable]
public class VoxelSample
{
    public int index;
    public VoxelPosition position;
    public int type;
    public float slope;
    public float risk;
    public float cost;
}

[System.Serializable]
public class VoxelPosition
{
    public int x;
    public int y;
    public int z;
}

