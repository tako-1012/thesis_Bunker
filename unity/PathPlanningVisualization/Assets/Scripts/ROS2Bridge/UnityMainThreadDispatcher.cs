using UnityEngine;
using System.Collections;
using System.Collections.Generic;

/// <summary>
/// Unityメインスレッドでコルーチンを実行するためのディスパッチャー
/// </summary>
public class UnityMainThreadDispatcher : MonoBehaviour
{
    private static UnityMainThreadDispatcher _instance;
    private Queue<System.Action> _executionQueue = new Queue<System.Action>();
    
    public static UnityMainThreadDispatcher Instance()
    {
        if (_instance == null)
        {
            GameObject go = new GameObject("UnityMainThreadDispatcher");
            _instance = go.AddComponent<UnityMainThreadDispatcher>();
            DontDestroyOnLoad(go);
        }
        return _instance;
    }
    
    void Update()
    {
        lock (_executionQueue)
        {
            while (_executionQueue.Count > 0)
            {
                _executionQueue.Dequeue().Invoke();
            }
        }
    }
    
    public void Enqueue(System.Action action)
    {
        lock (_executionQueue)
        {
            _executionQueue.Enqueue(action);
        }
    }
    
    public void Enqueue(IEnumerator coroutine)
    {
        Enqueue(() => StartCoroutine(coroutine));
    }
}


