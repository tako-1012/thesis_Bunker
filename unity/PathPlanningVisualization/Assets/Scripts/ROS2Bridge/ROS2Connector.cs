using UnityEngine;
using System.Collections.Generic;
using System.Net.Sockets;
using System.Text;
using System.Threading;

/// <summary>
/// ROS2データを受信するUnity側ブリッジ
/// </summary>
public class ROS2Bridge : MonoBehaviour
{
    [Header("Connection Settings")]
    public int port = 11000;
    public bool autoConnect = true;
    
    [Header("References")]
    public SimulationManager simulationManager;
    
    private TcpListener tcpListener;
    private TcpClient client;
    private NetworkStream stream;
    private Thread receiveThread;
    private bool isConnected = false;
    private bool shouldStop = false;
    
    void Start()
    {
        if (autoConnect)
        {
            StartServer();
        }
    }
    
    void StartServer()
    {
        try
        {
            tcpListener = new TcpListener(System.Net.IPAddress.Any, port);
            tcpListener.Start();
            
            Debug.Log($"ROS2 Bridge server started on port {port}");
            
            // 接続待機を別スレッドで実行
            Thread acceptThread = new Thread(AcceptClients);
            acceptThread.Start();
        }
        catch (System.Exception e)
        {
            Debug.LogError($"Failed to start server: {e.Message}");
        }
    }
    
    void AcceptClients()
    {
        while (!shouldStop)
        {
            try
            {
                client = tcpListener.AcceptTcpClient();
                stream = client.GetStream();
                isConnected = true;
                
                Debug.Log("ROS2 client connected");
                
                // データ受信を別スレッドで実行
                receiveThread = new Thread(ReceiveData);
                receiveThread.Start();
            }
            catch (System.Exception e)
            {
                if (!shouldStop)
                {
                    Debug.LogError($"Accept error: {e.Message}");
                }
            }
        }
    }
    
    void ReceiveData()
    {
        byte[] buffer = new byte[4096];
        
        while (isConnected && !shouldStop)
        {
            try
            {
                int bytesRead = stream.Read(buffer, 0, buffer.Length);
                if (bytesRead > 0)
                {
                    string data = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                    ProcessReceivedData(data);
                }
            }
            catch (System.Exception e)
            {
                Debug.LogError($"Receive error: {e.Message}");
                isConnected = false;
            }
        }
    }
    
    void ProcessReceivedData(string data)
    {
        // 複数のJSONメッセージが含まれる可能性があるため分割
        string[] messages = data.Split('\n');
        
        foreach (string message in messages)
        {
            if (string.IsNullOrEmpty(message)) continue;
            
            try
            {
                var jsonData = JsonUtility.FromJson<ROS2Message>(message);
                HandleROS2Message(jsonData);
            }
            catch (System.Exception e)
            {
                Debug.LogError($"JSON parse error: {e.Message}");
            }
        }
    }
    
    void HandleROS2Message(ROS2Message message)
    {
        switch (message.type)
        {
            case "path":
                HandlePathMessage(message);
                break;
            case "scenario":
                HandleScenarioMessage(message);
                break;
            case "pointcloud":
                HandlePointCloudMessage(message);
                break;
            default:
                Debug.LogWarning($"Unknown message type: {message.type}");
                break;
        }
    }
    
    void HandlePathMessage(ROS2Message message)
    {
        if (simulationManager == null) return;
        
        // 経路データをVector3配列に変換
        List<Vector3> pathPoints = new List<Vector3>();
        
        if (message.path != null)
        {
            foreach (var point in message.path)
            {
                pathPoints.Add(new Vector3(point.x, point.z, point.y)); // Unity座標系に変換
            }
        }
        
        // メインスレッドで実行
        UnityMainThreadDispatcher.Instance().Enqueue(() => {
            simulationManager.pathVisualizer.SetPath(pathPoints);
        });
    }
    
    void HandleScenarioMessage(ROS2Message message)
    {
        if (simulationManager == null) return;
        
        int scenarioId = message.scenario_id;
        
        // メインスレッドで実行
        UnityMainThreadDispatcher.Instance().Enqueue(() => {
            simulationManager.LoadScenario(scenarioId);
        });
    }
    
    void HandlePointCloudMessage(ROS2Message message)
    {
        Debug.Log($"Received pointcloud with {message.count} points");
        // 点群データの処理は後で実装
    }
    
    void OnDestroy()
    {
        shouldStop = true;
        isConnected = false;
        
        if (receiveThread != null)
        {
            receiveThread.Join();
        }
        
        if (stream != null)
        {
            stream.Close();
        }
        
        if (client != null)
        {
            client.Close();
        }
        
        if (tcpListener != null)
        {
            tcpListener.Stop();
        }
    }
}

[System.Serializable]
public class ROS2Message
{
    public string type;
    public PathPoint[] path;
    public int scenario_id;
    public int count;
    public long timestamp;
}

[System.Serializable]
public class PathPoint
{
    public float x;
    public float y;
    public float z;
}


